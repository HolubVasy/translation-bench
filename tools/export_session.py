#!/usr/bin/env python3
"""Export one benchmark session as a public protocol for the showcase page.

Raw facts only: scores, typed flags (criterion, type, severity), prices per
million tokens, token counts, word counts, calibration catches. No source or
translated text, no quotes, no segment ids, papers named A, B, C. Every
derived number (means, floors, price per 1000 words, levels) is computed by
the reader. ASCII only.

Usage: python tools/export_session.py <session-id> <data-dir> <out-dir>
"""
import glob
import json
import re
import sys
from pathlib import Path

import yaml

CRITERIA = ("meaning", "completeness", "data", "naturalness", "flow", "clean")
PAPERS = {"a1": "A", "a2": "B", "a3": "C"}
NAMES = {
    "anthropic/claude-opus-5.5": ("Claude Opus 5.5", "Anthropic"),
    "google/gemini-4-argon": ("Gemini 4 Argon", "Google"),
    "google/gemini-3.8-flash": ("Gemini 3.8 Flash", "Google"),
    "openai/gpt-6-sol-pro": ("GPT-6 Sol Pro", "OpenAI"),
    "openai/gpt-6-luna-pro": ("GPT-6 Luna Pro", "OpenAI"),
}
# List prices per 1M tokens where the measured price was a launch discount.
LIST_PRICES = {"google/gemini-4-argon": {"input": 4.0, "output": 20.0}}
LIMITS = [
    "Three scientific-technical papers, one run, equal criterion weights.",
    "The ranking may differ for other kinds of documents.",
    "Prices are per million tokens on the measurement date; list prices are given where a launch discount applied.",
    "The pipeline was built with Claude, and an Anthropic model won.",
]


def word_count(source):
    return sum(len(re.findall(r"\S+", s.get("text", ""))) for s in source["segments"])


def model_card(model_id):
    name, vendor = NAMES.get(model_id, (model_id, model_id.split("/")[0]))
    return {"model": model_id, "name": name, "vendor": vendor}


def translators(cfg, data):
    out = {}
    for code, model_id in cfg["translators"].items():
        card = model_card(model_id)
        price = cfg["prices"][code]
        card["price_per_mtok"] = {"input": price["input"], "output": price["output"]}
        card["list_price_per_mtok"] = LIST_PRICES.get(model_id, card["price_per_mtok"])
        card["tokens"] = {}
        for art, paper in PAPERS.items():
            usage = json.load(open(data / "translations" / ("tr__%s__%s.json" % (art, code))))["usage"]
            card["tokens"][paper] = {"input": usage["prompt_tokens"], "output": usage["completion_tokens"]}
        out[code] = card
    return out


def judges(cfg, data):
    out = {}
    for code, model_id in cfg["judges"].items():
        card = model_card(model_id)
        cal = json.load(open(data / "calibration" / ("cal__by__%s.json" % code)))
        card["calibration"] = {"planted": len(cal["planted"]), "caught": len(cal["caught"]),
                               "needed": cal["needed"], "passed": cal["passed"]}
        out[code] = card
    return out


def verdicts(data):
    rows = []
    for path in sorted(glob.glob(str(data / "judgments" / "ev__a*__by__J*.json"))):
        ev = json.load(open(path))
        if ev.get("pass", "forward") != "forward":
            continue  # reverse pass of double_pass judging: the report counts forward only
        paper = PAPERS[ev["article"]]
        for code, scores in ev["scores"].items():
            flags = [{"criterion": f.get("criterion"), "type": f.get("type"), "severity": f.get("severity")}
                     for f in ev.get("flags") or [] if f.get("translator") == code]
            rows.append({"paper": paper, "judge": ev["judge"], "translator": code,
                         "scores": {c: float(scores[c]) for c in CRITERIA}, "flags": flags})
    return rows


def main(session_id, data_dir, out_dir):
    data, out = Path(data_dir), Path(out_dir)
    cfg = yaml.safe_load(open(Path(data_dir).resolve().parent / "config.yaml"))
    session = {
        "session": session_id,
        "criteria": list(CRITERIA),
        "scale": {"min": 0, "max": 10},
        "papers": [{"id": PAPERS[a], "words": word_count(json.load(open(data / "source" / (a + ".json")))),
                    "kind": "scientific-technical"} for a in PAPERS],
        "translators": translators(cfg, data),
        "judges": judges(cfg, data),
        "limits": LIMITS,
    }
    folder = out / "sessions" / session_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "session.json").write_text(json.dumps(session, indent=1, ensure_ascii=True))
    (folder / "verdicts.json").write_text(json.dumps(verdicts(data), indent=1, ensure_ascii=True))
    index_path = out / "sessions" / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"sessions": []}
    if session_id not in index["sessions"]:
        index["sessions"].append(session_id)
    index["latest"] = sorted(index["sessions"])[-1]
    index_path.write_text(json.dumps(index, indent=1, ensure_ascii=True))
    print("exported", folder)


if __name__ == "__main__":
    main(*sys.argv[1:4])
