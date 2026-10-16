"""Run judge models: each judge sees one article and all its translations,
blind M codes only, in a per-round shuffled order.

Usage: python -m src.judge
Writes data/judgments/ev__a{n}__by__{J}.json (the shuffle order is stored
inside each file). Existing outputs are skipped, so the run can be resumed.
"""

import json
import random
import sys
from pathlib import Path

import yaml

from . import prompts
from .openrouter import chat, extract_json

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
OUT_DIR = Path("data/judgments")

CRITERIA = ("meaning", "completeness", "data", "naturalness", "flow", "clean")


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def strip_for_judge(translation):
    """Judges must not see usage or anything beyond the translated segments."""
    return {
        "article": translation["article"],
        "segments": translation["segments"],
    }


def validate_judgment(result, codes):
    errors = []
    ranking = result.get("ranking", [])
    if sorted(ranking) != sorted(codes):
        errors.append("ranking is not a permutation of %s" % ",".join(codes))
    scores = result.get("scores", {})
    for code in codes:
        row = scores.get(code)
        if not isinstance(row, dict):
            errors.append("no scores for %s" % code)
            continue
        for criterion in CRITERIA:
            value = row.get(criterion)
            if not isinstance(value, (int, float)) or not 0 <= value <= 10:
                errors.append("%s.%s out of range" % (code, criterion))
        row["total"] = sum(row.get(c, 0) for c in CRITERIA)
    return errors


def judge_one(cfg, article, judge_code, model, source_str, shuffled):
    prompt = prompts.build_judge_prompt(cfg, article, judge_code, source_str, shuffled)
    req = cfg["request"]
    codes = [code for code, _ in shuffled]
    last_errors = None
    for attempt in range(1, req["max_retries"] + 1):
        text, usage = chat(
            model,
            prompt,
            temperature=req["temperature"],
            timeout=req["timeout_sec"],
            max_retries=1,
        )
        try:
            result = extract_json(text)
        except (ValueError, json.JSONDecodeError) as err:
            last_errors = ["bad JSON: %s" % err]
            continue
        errors = validate_judgment(result, codes)
        if not errors:
            result["article"] = article
            result["judge"] = judge_code
            result["presentation_order"] = codes
            result["usage"] = usage
            return result
        last_errors = errors
    raise RuntimeError(
        "judge %s on article %s: %s" % (model, article, "; ".join(last_errors[:5]))
    )


def main():
    cfg = load_cfg()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    articles = sorted(SRC_DIR.glob("a*.json"))
    if not articles:
        print("no sources; run src.convert first")
        return 1
    failures = 0
    for article_path in articles:
        article = article_path.stem
        source_str = article_path.read_text(encoding="utf-8")
        translations = {}
        for code in cfg["translators"]:
            tr_path = TR_DIR / ("tr__%s__%s.json" % (article, code))
            if not tr_path.exists():
                print("missing %s, run src.translate first" % tr_path.name)
                return 1
            body = strip_for_judge(json.loads(tr_path.read_text(encoding="utf-8")))
            translations[code] = json.dumps(body, ensure_ascii=False, indent=1)
        for judge_code, model in cfg["judges"].items():
            out = OUT_DIR / ("ev__%s__by__%s.json" % (article, judge_code))
            if out.exists():
                print("skip %s (exists)" % out.name)
                continue
            rng = random.Random("%s-%s" % (article, judge_code))
            codes = list(translations)
            rng.shuffle(codes)
            shuffled = [(code, translations[code]) for code in codes]
            print("judge %s on %s (%s) ..." % (judge_code, article, model))
            try:
                result = judge_one(cfg, article, judge_code, model, source_str, shuffled)
            except Exception as err:  # noqa: BLE001
                failures += 1
                print("  FAILED: %s" % err)
                continue
            out.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("  ok -> %s" % out.name)
    if failures:
        print("%d judgment(s) failed; rerun to retry only those" % failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
