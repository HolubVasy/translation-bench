"""Second pass over existing translations: one model translates, another proofreads.

Usage: python -m src.refine [a1 a2 ...]
Reads config "hybrids": code -> {base: translator code, model: proofreader model,
source: true if the proofreader also sees the source}. For every article reads
data/translations/tr__aN__<base>.json and writes tr__aN__<hybrid code>.json.
The usage stored is the second pass only; the base translation keeps its own.
Already existing outputs are skipped, so the run can be resumed.
"""

import json
import sys
from pathlib import Path

from . import prompts
from .openrouter import (OpenRouterError, ValidationFailed, add_usage, chat,
                         extract_json, key_usage, log_spend, run_stamp)
from .translate import OUT_DIR, SRC_DIR, load_cfg, validate_translation

SOURCE_RULE = " Check the translation against the source and also fix places where it does not match it."


def build_prompt(cfg, source, translation, sees_source):
    """Same prompt for both variants; only the source block differs."""
    body = {"segments": translation["segments"]}
    source_block = ""
    if sees_source:
        source_block = "\nSOURCE:\n%s\n" % json.dumps({"segments": source["segments"]}, ensure_ascii=False, indent=1)
    return prompts.load_skill("refiner").substitute(
        source_lang=cfg["source_lang"],
        target_lang=cfg["target_lang"],
        source_rule=SOURCE_RULE if sees_source else "",
        source_block=source_block,
        translation_json=json.dumps(body, ensure_ascii=False, indent=1),
    )


def refine_one(cfg, source, translation, code, spec):
    """One proofreading call with retries; returns the validated result."""
    prompt = build_prompt(cfg, source, translation, bool(spec.get("source")))
    req = cfg["request"]
    spent, last_errors = {}, None
    for _ in range(req["max_retries"]):
        try:
            text, usage = chat(spec["model"], prompt, temperature=req["temperature"],
                               timeout=req["timeout_sec"], max_retries=1, max_tokens=req.get("max_tokens"))
        except OpenRouterError as err:
            last_errors = ["transport: %s" % err]
            continue
        add_usage(spent, usage)
        try:
            result = extract_json(text)
        except (ValueError, json.JSONDecodeError) as err:
            last_errors = ["bad JSON: %s" % err]
            continue
        errors = validate_translation(source, result)
        if not errors:
            result.update({"article": source["article"], "translator": code, "base": spec["base"],
                           "refiner": spec["model"], "sees_source": bool(spec.get("source")), "usage": spent})
            return result
        last_errors = errors
    raise ValidationFailed("%s on article %s: %s" % (code, source["article"], "; ".join(last_errors[:5])), spent)


def refine_article(cfg, article_path, hybrids):
    """Run every hybrid on one article; returns the number of failures."""
    source = json.loads(article_path.read_text(encoding="utf-8"))
    failures = 0
    for code, spec in hybrids.items():
        out = OUT_DIR / ("tr__%s__%s.json" % (article_path.stem, code))
        base = OUT_DIR / ("tr__%s__%s.json" % (article_path.stem, spec["base"]))
        if out.exists():
            print("skip %s (exists)" % out.name)
            continue
        if not base.exists():
            print("skip %s: no base translation %s" % (out.name, base.name))
            failures += 1
            continue
        print("refine %s with %s (%s over %s) ..." % (article_path.stem, code, spec["model"], spec["base"]))
        try:
            result = refine_one(cfg, source, json.loads(base.read_text(encoding="utf-8")), code, spec)
        except ValidationFailed as err:
            failures += 1
            print("  FAILED: %s" % err)
            fail = OUT_DIR / ("fail__%s__%s__%s.json" % (article_path.stem, code, run_stamp()))
            fail.write_text(json.dumps({"article": article_path.stem, "translator": code,
                                        "error": str(err), "usage": err.usage}))
            continue
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  ok -> %s" % out.name)
    return failures


def main(argv):
    cfg = load_cfg()
    hybrids = cfg.get("hybrids") or {}
    if not hybrids:
        print("no hybrids in config.yaml, nothing to refine")
        return 0
    articles = sorted(SRC_DIR.glob("a*.json"))
    if argv:
        articles = [p for p in articles if p.stem in set(argv)]
    usage_before = key_usage()
    failures = sum(refine_article(cfg, p, hybrids) for p in articles)
    log_spend("refine", usage_before, key_usage())
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
