"""Run all translator models over all source articles.

Usage: python -m src.translate [a1 a2 ...]
Reads data/source/a*.json, writes data/translations/tr__a{n}__{code}.json.
Already existing outputs are skipped, so the run can be resumed.
"""

import json
import sys
from pathlib import Path

import yaml

from . import prompts
from .openrouter import ValidationFailed, add_usage, chat, extract_json

SRC_DIR = Path("data/source")
OUT_DIR = Path("data/translations")


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def validate_translation(source, result):
    """Same ids, same order, same types; text non-empty; image placeholders kept."""
    errors = []
    src_segs = source["segments"]
    out_segs = result.get("segments", [])
    if len(src_segs) != len(out_segs):
        errors.append("segment count %d != %d" % (len(out_segs), len(src_segs)))
        return errors
    for src, out in zip(src_segs, out_segs):
        if out.get("id") != src["id"]:
            errors.append("id mismatch: %s vs %s" % (out.get("id"), src["id"]))
            continue
        if out.get("type") != src["type"]:
            errors.append("%s: type changed" % src["id"])
        if src["type"] == "image" and out.get("text") != src["text"]:
            errors.append("%s: image placeholder changed" % src["id"])
        if not str(out.get("text", "")).strip():
            errors.append("%s: empty text" % src["id"])
    return errors


def translate_one(cfg, article_path, code, model):
    source = json.loads(article_path.read_text(encoding="utf-8"))
    article_json = json.dumps(source, ensure_ascii=False, indent=1)
    prompt = prompts.build_translator_prompt(cfg, article_json)
    req = cfg["request"]
    last_errors = None
    spent = {}
    for attempt in range(1, req["max_retries"] + 1):
        text, usage = chat(
            model,
            prompt,
            temperature=req["temperature"],
            timeout=req["timeout_sec"],
            max_retries=1,
            max_tokens=req.get("max_tokens"),
        )
        add_usage(spent, usage)
        try:
            result = extract_json(text)
        except (ValueError, json.JSONDecodeError) as err:
            last_errors = ["bad JSON: %s" % err]
            continue
        errors = validate_translation(source, result)
        if not errors:
            result["article"] = source["article"]
            result["translator"] = code
            result["usage"] = spent
            return result
        last_errors = errors
    raise ValidationFailed(
        "%s on article %s: validation failed: %s"
        % (model, source["article"], "; ".join(last_errors[:5])),
        spent,
    )


def main(argv):
    cfg = load_cfg()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    articles = sorted(SRC_DIR.glob("a*.json"))
    if argv:
        wanted = set(argv)
        articles = [p for p in articles if p.stem in wanted]
    if not articles:
        print("no source articles in %s; run src.convert first" % SRC_DIR)
        return 1
    failures = 0
    for article_path in articles:
        for code, model in cfg["translators"].items():
            out = OUT_DIR / ("tr__%s__%s.json" % (article_path.stem, code))
            if out.exists():
                print("skip %s (exists)" % out.name)
                continue
            print("translate %s with %s (%s) ..." % (article_path.stem, code, model))
            try:
                result = translate_one(cfg, article_path, code, model)
            except ValidationFailed as err:
                failures += 1
                print("  FAILED: %s" % err)
                fail = OUT_DIR / ("fail__%s__%s.json" % (article_path.stem, code))
                fail.write_text(json.dumps({"article": article_path.stem, "translator": code,
                                            "error": str(err), "usage": err.usage}))
                continue
            except Exception as err:  # noqa: BLE001
                failures += 1
                print("  FAILED: %s" % err)
                continue
            out.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("  ok -> %s" % out.name)
    if failures:
        print("%d translation(s) failed; rerun to retry only those" % failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
