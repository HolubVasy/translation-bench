"""Judge calibration with a planted decoy.

One real translation is copied and errors are planted in it on purpose.
Coarse ones (a changed number, a dropped sentence) and subtle ones (a
flipped negation, a changed modality, a dropped "only") are mixed, so the
report shows not only whether a judge catches errors but which kind.
The answer key goes to data/calibration/decoy__a{n}.json and .md. Each
judge reviews the decoy alone under a neutral blind label. A judge that
flags fewer than `min_caught` planted segments fails calibration and is
left out of the overall tables.

Settings: `calibration` block in config.yaml (kinds, min_caught, label).
Usage: python -m src.calibrate
"""

import copy
import json
import re
import sys
from pathlib import Path

import yaml

from . import prompts
from .judge import strip_for_judge, validate_judgment
from .openrouter import add_usage, chat, extract_json, key_usage, log_spend, run_stamp
from .preflight import load_glossary

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
OUT_DIR = Path("data/calibration")

NUM_RE = re.compile(r"\d+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

NEGATION_SWAPS = [(" is not ", " is "), (" are not ", " are "), (" does not ", " does "),
                  (" do not ", " do "), (" cannot ", " can "), (" not ", " "),
                  (" is ", " is not "), (" are ", " are not "), (" can ", " cannot "),
                  (" will ", " will not "), (" has ", " has not ")]
MODALITY_SWAPS = [(" may ", " must "), (" might ", " will "), (" should ", " must "),
                  (" could ", " did "), (" must ", " may "), (" can ", " must ")]
QUANTIFIER_SWAPS = [(" only ", " "), (" all ", " some "), (" always ", " sometimes "),
                    (" never ", " rarely "), (" every ", " some "), (" most ", " few ")]


# ------------------------------------------------------------ loaders


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def calibration_settings(cfg):
    cal = dict(cfg.get("calibration") or {})
    cal.setdefault("article", "a1")
    cal.setdefault("base_translator", "M4")
    cal.setdefault("label", "M6")
    cal.setdefault("min_caught", 2)
    cal.setdefault("kinds", ["negation", "number", "omission", "modality"])
    return cal


# ------------------------------------------------------------ planters


def _swap_first(seg, swaps, kind):
    for old, new in swaps:
        if old in seg["text"]:
            before = seg["text"]
            seg["text"] = before.replace(old, new, 1)
            return {"segment": seg["id"], "kind": kind, "before": before, "after": seg["text"]}
    return None


def plant_negation(seg):
    return _swap_first(seg, NEGATION_SWAPS, "negation")


def plant_modality(seg):
    return _swap_first(seg, MODALITY_SWAPS, "modality")


def plant_quantifier(seg):
    return _swap_first(seg, QUANTIFIER_SWAPS, "quantifier")


def plant_number(seg):
    match = NUM_RE.search(seg["text"])
    if not match:
        return None
    value = int(match.group(0))
    changed = str(value + (10 if value < 1000 else 3))
    before = seg["text"]
    seg["text"] = before[: match.start()] + changed + before[match.end():]
    return {"segment": seg["id"], "kind": "number", "before": before, "after": seg["text"]}


def plant_omission(seg):
    before = seg["text"]
    sentences = SENTENCE_SPLIT_RE.split(before)
    if len(sentences) >= 2:
        seg["text"] = sentences[0]
    else:
        words = before.split()
        if len(words) < 8:
            return None
        seg["text"] = " ".join(words[: len(words) // 2]) + "."
    return {"segment": seg["id"], "kind": "omission", "before": before, "after": seg["text"]}


PLANTERS = {
    "negation": plant_negation,
    "number": plant_number,
    "omission": plant_omission,
    "modality": plant_modality,
    "quantifier": plant_quantifier,
}


# ------------------------------------------------------------ logic


def make_decoy(translation, kinds=("negation", "number", "omission", "modality")):
    """Return (decoy, planted). Each kind goes into a different paragraph;
    omission prefers the longest paragraph."""
    decoy = copy.deepcopy(translation)
    paragraphs = [s for s in decoy["segments"] if s["type"] == "p"]
    used, planted = set(), []
    for kind in kinds:
        planter = PLANTERS[kind]
        pool = sorted(paragraphs, key=lambda s: -len(s["text"])) if kind == "omission" else paragraphs
        result = _plant_in_first_free(planter, pool, used)
        if result:
            planted.append(result)
    return decoy, planted


def _plant_in_first_free(planter, pool, used):
    for seg in pool:
        if seg["id"] in used:
            continue
        result = planter(seg)
        if result:
            used.add(seg["id"])
            return result
    return None


def score_catches(judgment, planted, label):
    flagged = {str(f.get("segment", "")).strip() for f in judgment.get("flags", [])
               if str(f.get("translator", label)).strip() == label}
    return [p["segment"] for p in planted if p["segment"] in flagged]


def caught_by_kind(planted, caught):
    return {p["kind"]: p["segment"] in caught for p in planted}


# ------------------------------------------------------------ writers


def write_answer_key(article, base, label, planted):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key = {"article": article, "base_translator": base, "label": label, "planted": planted}
    (OUT_DIR / ("decoy__%s.json" % article)).write_text(
        json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Decoy answer key, article %s" % article, "",
             "Base translation: %s. Shown to judges as %s." % (base, label), ""]
    for p in planted:
        lines += ["## %s in %s" % (p["kind"], p["segment"]), "",
                  "Before: %s" % p["before"], "", "After: %s" % p["after"], ""]
    (OUT_DIR / ("decoy__%s.md" % article)).write_text("\n".join(lines), encoding="utf-8")


def write_result(judge_code, article, label, planted, judgment, needed):
    caught = score_catches(judgment, planted, label)
    record = {"judge": judge_code, "article": article, "label": label,
              "planted": [p["segment"] for p in planted], "caught": caught,
              "by_kind": caught_by_kind(planted, caught),
              "needed": needed, "passed": len(caught) >= needed,
              "judgment": judgment, "usage": judgment.get("usage", {})}
    (OUT_DIR / ("cal__by__%s.json" % judge_code)).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def write_failure(judge_code, spent):
    (OUT_DIR / ("fail__cal__by__%s__%s.json" % (judge_code, run_stamp()))).write_text(
        json.dumps({"judge": judge_code, "usage": spent}))


# ------------------------------------------------------------ API round


def judge_decoy(cfg, article, judge_code, model, source_str, label, decoy_str, glossary):
    prompt = prompts.build_judge_prompt(cfg, article, judge_code, source_str,
                                        [(label, decoy_str)], glossary)
    req = cfg["request"]
    spent = {}
    for _ in range(req["max_retries"]):
        try:
            text, usage = chat(model, prompt, temperature=req["temperature"],
                               timeout=req["timeout_sec"], max_retries=1,
                               max_tokens=req.get("max_tokens"))
            add_usage(spent, usage)
            candidate = extract_json(text)
        except Exception as err:  # noqa: BLE001
            print("  retry: %s" % err)
            continue
        errors = validate_judgment(candidate, [label])
        if not errors:
            candidate["usage"] = spent
            return candidate
        print("  retry: %s" % "; ".join(errors[:3]))
    write_failure(judge_code, spent)
    return None


# ------------------------------------------------------------ main


def main():
    cfg = load_cfg()
    cal = calibration_settings(cfg)
    if not cal.get("enabled", True):
        print("calibration disabled in config.yaml")
        return 0
    article, base, label = cal["article"], cal["base_translator"], cal["label"]
    tr_path = TR_DIR / ("tr__%s__%s.json" % (article, base))
    src_path = SRC_DIR / ("%s.json" % article)
    if not tr_path.exists() or not src_path.exists():
        print("calibration needs %s and %s" % (src_path, tr_path))
        return 1
    base_translation = strip_for_judge(json.loads(tr_path.read_text(encoding="utf-8")))
    decoy, planted = make_decoy(base_translation, cal["kinds"])
    if not planted:
        print("could not plant any error into %s; pick another base_translator" % tr_path.name)
        return 1
    write_answer_key(article, base, label, planted)
    needed = min(int(cal["min_caught"]), len(planted))
    source_str = src_path.read_text(encoding="utf-8")
    decoy_str = json.dumps(decoy, ensure_ascii=False, indent=1)
    glossary = load_glossary(cfg)
    usage_before = key_usage()
    failures = 0
    for judge_code, model in cfg["judges"].items():
        if (OUT_DIR / ("cal__by__%s.json" % judge_code)).exists():
            print("skip cal__by__%s.json (exists)" % judge_code)
            continue
        print("calibrate %s (%s) ..." % (judge_code, model))
        judgment = judge_decoy(cfg, article, judge_code, model, source_str, label, decoy_str, glossary)
        if judgment is None:
            failures += 1
            print("  FAILED")
            continue
        record = write_result(judge_code, article, label, planted, judgment, needed)
        print("  caught %d/%d -> %s" % (len(record["caught"]), len(planted),
                                        "pass" if record["passed"] else "FAIL"))
    log_spend("calibrate", usage_before, key_usage())
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
