"""Judge calibration with a planted decoy.

One real translation is copied and three errors are planted in it on
purpose: a flipped negation, a changed number and a truncated paragraph.
The planted errors are recorded in data/calibration/decoy__a{n}.json and
.md (the answer key). Each judge then reviews the decoy alone, under a
neutral blind label, with the usual judge skill. A judge that flags fewer
than `min_caught` of the planted segments fails calibration and is left
out of the overall tables in the report.

Settings: `calibration` block in config.yaml.
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
from .openrouter import chat, extract_json

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
OUT_DIR = Path("data/calibration")

NEGATED = [(" is not ", " is "), (" are not ", " are "), (" does not ", " does "),
           (" do not ", " do "), (" cannot ", " can "), (" not ", " ")]
AFFIRMED = [(" is ", " is not "), (" are ", " are not "), (" can ", " cannot "),
            (" will ", " will not "), (" has ", " has not ")]
NUM_RE = re.compile(r"\d+")


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def _plant_negation(seg):
    for old, new in NEGATED + AFFIRMED:
        if old in seg["text"]:
            before = seg["text"]
            seg["text"] = before.replace(old, new, 1)
            return {"segment": seg["id"], "kind": "negation", "before": before, "after": seg["text"]}
    return None


def _plant_number(seg):
    match = NUM_RE.search(seg["text"])
    if not match:
        return None
    value = int(match.group(0))
    changed = str(value + (10 if value < 1000 else 3))
    before = seg["text"]
    seg["text"] = before[: match.start()] + changed + before[match.end():]
    return {"segment": seg["id"], "kind": "number", "before": before, "after": seg["text"]}


def _plant_omission(seg):
    before = seg["text"]
    sentences = re.split(r"(?<=[.!?])\s+", before)
    if len(sentences) >= 2:
        seg["text"] = sentences[0]
    else:
        words = before.split()
        if len(words) < 8:
            return None
        seg["text"] = " ".join(words[: len(words) // 2]) + "."
    return {"segment": seg["id"], "kind": "omission", "before": before, "after": seg["text"]}


def make_decoy(translation):
    """Return (decoy, planted). Each error goes into a different paragraph."""
    decoy = copy.deepcopy(translation)
    paras = [s for s in decoy["segments"] if s["type"] == "p"]
    used = set()
    planted = []
    for planter, pool in (
        (_plant_negation, paras),
        (_plant_number, paras),
        (_plant_omission, sorted(paras, key=lambda s: -len(s["text"]))),
    ):
        for seg in pool:
            if seg["id"] in used:
                continue
            result = planter(seg)
            if result:
                used.add(seg["id"])
                planted.append(result)
                break
    return decoy, planted


def score_catches(judgment, planted, label):
    flagged = {
        str(f.get("segment", "")).strip()
        for f in judgment.get("flags", [])
        if str(f.get("translator", label)).strip() == label
    }
    return [p["segment"] for p in planted if p["segment"] in flagged]


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


def main():
    cfg = load_cfg()
    cal = cfg.get("calibration") or {}
    if not cal.get("enabled", True):
        print("calibration disabled in config.yaml")
        return 0
    article = cal.get("article", "a1")
    base = cal.get("base_translator", "M4")
    label = cal.get("label", "M6")
    min_caught = int(cal.get("min_caught", 2))

    tr_path = TR_DIR / ("tr__%s__%s.json" % (article, base))
    src_path = SRC_DIR / ("%s.json" % article)
    if not tr_path.exists() or not src_path.exists():
        print("calibration needs %s and %s" % (src_path, tr_path))
        return 1
    decoy, planted = make_decoy(strip_for_judge(json.loads(tr_path.read_text(encoding="utf-8"))))
    if not planted:
        print("could not plant any error into %s; pick another base_translator" % tr_path.name)
        return 1
    write_answer_key(article, base, label, planted)
    needed = min(min_caught, len(planted))

    source_str = src_path.read_text(encoding="utf-8")
    decoy_str = json.dumps(decoy, ensure_ascii=False, indent=1)
    req = cfg["request"]
    failures = 0
    for judge_code, model in cfg["judges"].items():
        out = OUT_DIR / ("cal__by__%s.json" % judge_code)
        if out.exists():
            print("skip %s (exists)" % out.name)
            continue
        prompt = prompts.build_judge_prompt(cfg, article, judge_code, source_str, [(label, decoy_str)])
        print("calibrate %s (%s) ..." % (judge_code, model))
        result = None
        for _ in range(req["max_retries"]):
            try:
                text, usage = chat(model, prompt, temperature=req["temperature"],
                                   timeout=req["timeout_sec"], max_retries=1,
                                   max_tokens=req.get("max_tokens"))
                candidate = extract_json(text)
            except Exception as err:  # noqa: BLE001
                print("  retry: %s" % err)
                continue
            if not validate_judgment(candidate, [label]):
                candidate["usage"] = usage
                result = candidate
                break
        if result is None:
            failures += 1
            print("  FAILED")
            continue
        caught = score_catches(result, planted, label)
        record = {"judge": judge_code, "article": article, "label": label,
                  "planted": [p["segment"] for p in planted], "caught": caught,
                  "needed": needed, "passed": len(caught) >= needed,
                  "judgment": result, "usage": result.get("usage", {})}
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  caught %d/%d -> %s" % (len(caught), len(planted),
                                        "pass" if record["passed"] else "FAIL"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
