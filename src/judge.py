"""Run judge models: each judge sees one article and all its admitted
translations, blind M codes only, in a seeded shuffled order.

With judging.double_pass the judge sees the same set a second time in the
reversed order, which lets the report measure position bias. Translations
disqualified by mech_check gates are not sent to judges.

Usage: python -m src.judge
Writes data/judgments/ev__a{n}__by__{J}.json and, for the reversed pass,
ev__a{n}__by__{J}__r.json. Existing outputs are skipped (resumable).
"""

import json
import random
import sys
from pathlib import Path

import yaml

from . import prompts
from .openrouter import (OpenRouterError, ValidationFailed, add_usage, chat,
                         extract_json, key_usage, log_spend, run_stamp)
from .preflight import load_glossary

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
CHECK_DIR = Path("data/checks")
OUT_DIR = Path("data/judgments")

CRITERIA = ("meaning", "completeness", "data", "naturalness", "flow", "clean")
PASSES = {"forward": "", "reverse": "__r"}


# ------------------------------------------------------------ loaders


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def load_translation(article, code):
    path = TR_DIR / ("tr__%s__%s.json" % (article, code))
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def is_disqualified(article, code):
    """Gate verdict for one translation; the check stage must have run."""
    path = CHECK_DIR / ("mech__%s__%s.json" % (article, code))
    if not path.exists():
        raise FileNotFoundError("%s, run src.mech_check first" % path.name)
    return bool(json.loads(path.read_text(encoding="utf-8")).get("disqualified", False))


def admitted_translations(cfg, article):
    """code -> judge-ready JSON string for every translation not gated out."""
    out = {}
    for code in cfg["translators"]:
        translation = load_translation(article, code)
        if translation is None:
            raise FileNotFoundError("tr__%s__%s.json, run src.translate first" % (article, code))
        if is_disqualified(article, code):
            continue
        out[code] = json.dumps(strip_for_judge(translation), ensure_ascii=False, indent=1)
    return out


# ------------------------------------------------------------ logic


def strip_for_judge(translation):
    """Judges must not see usage or anything beyond the translated segments."""
    return {"article": translation["article"], "segments": translation["segments"]}


def validate_judgment(result, codes):
    """Problems with a judge reply, as data; a malformed reply is a list of
    problems, never an exception."""
    if not isinstance(result, dict):
        return ["reply is not a JSON object"]
    errors = []
    ranking = result.get("ranking")
    if not isinstance(ranking, list) or sorted(map(str, ranking)) != sorted(codes):
        errors.append("ranking is not a permutation of %s" % ",".join(codes))
    scores = result.get("scores")
    if not isinstance(scores, dict):
        return errors + ["scores is not an object"]
    for code in codes:
        errors += _validate_scores(code, scores.get(code))
    return errors


def _validate_scores(code, row):
    if not isinstance(row, dict):
        return ["no scores for %s" % code]
    errors = []
    for criterion in CRITERIA:
        value = row.get(criterion)
        if not isinstance(value, (int, float)) or not 0 <= value <= 10:
            errors.append("%s.%s out of range" % (code, criterion))
    row["total"] = sum(row.get(c, 0) for c in CRITERIA)
    return errors


def presentation_order(codes, article, judge_code, pass_name):
    """Seeded shuffle per round; the reverse pass is the exact mirror."""
    order = list(codes)
    random.Random("%s-%s" % (article, judge_code)).shuffle(order)
    return order[::-1] if pass_name == "reverse" else order


def planned_rounds(cfg, articles):
    passes = ["forward", "reverse"] if (cfg.get("judging") or {}).get("double_pass") else ["forward"]
    for article in articles:
        for judge_code, model in cfg["judges"].items():
            for pass_name in passes:
                yield article, judge_code, model, pass_name


def output_path(article, judge_code, pass_name):
    return OUT_DIR / ("ev__%s__by__%s%s.json" % (article, judge_code, PASSES[pass_name]))


# ------------------------------------------------------------ API round


def judge_round(cfg, article, judge_code, model, source_str, shuffled, glossary):
    """One judge call with retries; returns the validated judgment."""
    prompt = prompts.build_judge_prompt(cfg, article, judge_code, source_str, shuffled, glossary)
    req = cfg["request"]
    codes = [code for code, _ in shuffled]
    spent, last_errors = {}, None
    for _ in range(req["max_retries"]):
        try:
            text, usage = chat(model, prompt, temperature=req["temperature"],
                               timeout=req["timeout_sec"], max_retries=1,
                               max_tokens=req.get("max_tokens"))
        except OpenRouterError as err:
            last_errors = ["transport: %s" % err]
            continue
        add_usage(spent, usage)
        result, last_errors = _parse_round(text, codes)
        if result is not None:
            result["usage"] = spent
            return result
    raise ValidationFailed("judge %s on %s: %s" % (model, article, "; ".join(last_errors[:5])), spent)


def _parse_round(text, codes):
    try:
        result = extract_json(text)
    except ValueError as err:
        return None, ["bad JSON: %s" % err]
    errors = validate_judgment(result, codes)
    return (result, None) if not errors else (None, errors)


# ------------------------------------------------------------ writers


def write_judgment(path, result, article, judge_code, pass_name, codes):
    result.update({"article": article, "judge": judge_code, "pass": pass_name,
                   "presentation_order": codes})
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def write_failure(article, judge_code, pass_name, err):
    path = OUT_DIR / ("fail__%s__by__%s%s__%s.json" % (article, judge_code, PASSES[pass_name], run_stamp()))
    path.write_text(json.dumps({"article": article, "judge": judge_code, "pass": pass_name,
                                "error": str(err), "usage": err.usage}))


# ------------------------------------------------------------ main


def main():
    cfg = load_cfg()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    articles = sorted(p.stem for p in SRC_DIR.glob("a*.json"))
    if not articles:
        print("no sources; run src.convert first")
        return 1
    glossary = load_glossary(cfg)
    usage_before = key_usage()
    failures = 0
    for article, judge_code, model, pass_name in planned_rounds(cfg, articles):
        out = output_path(article, judge_code, pass_name)
        if out.exists():
            print("skip %s (exists)" % out.name)
            continue
        try:
            translations = admitted_translations(cfg, article)
        except FileNotFoundError as err:
            print("missing %s" % err)
            failures += 1
            break
        if len(translations) < 2:
            print("skip %s: fewer than two admitted translations" % out.name)
            continue
        codes = presentation_order(translations, article, judge_code, pass_name)
        shuffled = [(code, translations[code]) for code in codes]
        source_str = (SRC_DIR / ("%s.json" % article)).read_text(encoding="utf-8")
        print("judge %s on %s, %s pass (%s) ..." % (judge_code, article, pass_name, model))
        try:
            result = judge_round(cfg, article, judge_code, model, source_str, shuffled, glossary)
        except ValidationFailed as err:
            failures += 1
            write_failure(article, judge_code, pass_name, err)
            print("  FAILED: %s" % err)
            continue
        write_judgment(out, result, article, judge_code, pass_name, codes)
        print("  ok -> %s" % out.name)
    log_spend("judge", usage_before, key_usage())
    if failures:
        print("%d judgment(s) failed; rerun to retry only those" % failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
