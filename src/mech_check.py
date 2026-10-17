"""Deterministic checks and gates per translation.

Checks run per segment: numbers, URLs, placeholders, list markers,
glossary terms, source-script residue. Gates run per translation and can
disqualify it before any judge sees it: length ratio out of band, too
much source script left, too many glossary violations, any missing
segment. A disqualified translation is skipped by judge.py and listed in
the report. Thresholds live under `gates` in config.yaml.

Usage: python -m src.mech_check
Reads data/source and data/translations,
writes data/checks/mech__a{n}__{code}.json and prints a summary.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from .preflight import load_glossary

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
OUT_DIR = Path("data/checks")

NUM_RE = re.compile(r"\d+(?:[ \u00a0.,]\d+)*")
URL_RE = re.compile(r"https?://[^\s\)\]\>\"']+")
PLACEHOLDER_RE = re.compile(r"\[IMAGE_\d+\]")
LIST_MARKER_RE = re.compile(r"^(?:[-*]|\d+[.)])\s")
CYRILLIC_RE = re.compile("[\u0400-\u04ff]")
ENGLISH_FUNCTION_WORDS = frozenset(
    "the and of with which were that from this these was are is for by onto into "
    "their been have has than then there where while when".split())
WORD_RE = re.compile(r"[A-Za-z]+")


def count_cyrillic(text):
    """Cyrillic letters: untranslated Russian in a translation out of Russian."""
    return len(CYRILLIC_RE.findall(text)), "cyrillic chars"


def count_english_function_words(text):
    """English function words: untranslated English sentences survive as these.
    Names, units and abbreviations kept in Latin script do not count."""
    words = [w.lower() for w in WORD_RE.findall(text)]
    return sum(w in ENGLISH_FUNCTION_WORDS for w in words), "english function words"


RESIDUE_DETECTORS = {
    "Russian": count_cyrillic,
    "English": count_english_function_words,
}

DEFAULT_GATES = {
    "length_ratio": {"min": 0.6, "max": 1.8},
    "max_source_script_chars": 0,
    "max_glossary_violations": 3,
}


# ------------------------------------------------------------ loaders


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def load_sources():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in SRC_DIR.glob("a*.json")}


def load_translations():
    out = {}
    for path in sorted(TR_DIR.glob("tr__*.json")):
        _, article, code = path.stem.split("__")
        out[(article, code)] = json.loads(path.read_text(encoding="utf-8"))
    return out


# ------------------------------------------------------------ segment checks


def _normalize_number(num):
    """Canonical form: thousands separators (a space, or a comma or point
    followed by exactly three digits) are dropped, a decimal comma becomes a
    point. 1 000 000, 1,000,000 and 1.000.000 agree; 1,5 equals 1.5 and
    differs from 15."""
    num = re.sub(r"[ \u00a0]", "", num)
    num = re.sub(r"[.,](?=\d{3}(?:\D|$))", "", num)
    return num.replace(",", ".")


def _tokens(text, pattern, normalizer=None):
    found = pattern.findall(text)
    if normalizer:
        found = [normalizer(item) for item in found]
    return Counter(found)


def _diff_tokens(kind, src_text, out_text, pattern, normalizer=None):
    missing = _tokens(src_text, pattern, normalizer) - _tokens(out_text, pattern, normalizer)
    extra = _tokens(out_text, pattern, normalizer) - _tokens(src_text, pattern, normalizer)
    if not missing and not extra:
        return None
    return {"kind": kind, "missing": sorted(missing.elements()), "extra": sorted(extra.elements())}


def check_numbers(src_seg, out_seg, glossary):
    return _diff_tokens("numbers", src_seg["text"], out_seg["text"], NUM_RE, _normalize_number)


def check_urls(src_seg, out_seg, glossary):
    return _diff_tokens("urls", src_seg["text"], out_seg["text"], URL_RE)


def check_placeholders(src_seg, out_seg, glossary):
    return _diff_tokens("placeholders", src_seg["text"], out_seg["text"], PLACEHOLDER_RE)


def check_list_marker(src_seg, out_seg, glossary):
    """A segment that starts as a list item must still start as one."""
    src_is_item = bool(LIST_MARKER_RE.match(src_seg["text"]))
    out_is_item = bool(LIST_MARKER_RE.match(out_seg["text"]))
    if src_is_item == out_is_item:
        return None
    return {"kind": "list_marker", "missing": ["list marker"] if src_is_item else [],
            "extra": [] if src_is_item else ["list marker"]}


def check_glossary(src_seg, out_seg, glossary):
    """Every glossary term present in the source must appear in the
    translation in one of its approved target forms."""
    src_text = src_seg["text"].lower()
    out_text = out_seg["text"].lower()
    missing = [
        term["source"]
        for term in glossary
        if term["source"].lower() in src_text
        and not any(target.lower() in out_text for target in term["target"])
    ]
    if not missing:
        return None
    return {"kind": "glossary", "missing": missing, "extra": []}


RESIDUE = {"detector": count_cyrillic}  # set from config.source_lang in main()


def check_source_script(src_seg, out_seg, glossary):
    """Source-language residue left in the translation (untranslated text)."""
    if src_seg["type"] == "image":
        return None
    count, unit = RESIDUE["detector"](out_seg["text"])
    if not count:
        return None
    return {"kind": "source_script", "missing": [], "extra": ["%d %s" % (count, unit)]}


SEGMENT_CHECKS = {
    "numbers": check_numbers,
    "urls": check_urls,
    "placeholders": check_placeholders,
    "list_marker": check_list_marker,
    "glossary": check_glossary,
    "source_script": check_source_script,
}


def check_segments(source, translation, glossary):
    """All segment-level issues of one translation, each tagged with its segment."""
    issues = []
    tr_by_id = {seg["id"]: seg for seg in translation["segments"]}
    for src_seg in source["segments"]:
        out_seg = tr_by_id.get(src_seg["id"])
        if out_seg is None:
            issues.append({"segment": src_seg["id"], "kind": "missing_segment"})
            continue
        for check in SEGMENT_CHECKS.values():
            issue = check(src_seg, out_seg, glossary)
            if issue:
                issue["segment"] = src_seg["id"]
                issues.append(issue)
    return issues


# ------------------------------------------------------------ gates


def _word_count(segments):
    return sum(len(seg["text"].split()) for seg in segments if seg["type"] != "image")


def gate_length_ratio(source, translation, issues, limits):
    band = limits["length_ratio"]
    src_words = _word_count(source["segments"]) or 1
    ratio = _word_count(translation["segments"]) / src_words
    if band["min"] <= ratio <= band["max"]:
        return None
    return "length ratio %.2f outside %.2f..%.2f" % (ratio, band["min"], band["max"])


def gate_source_script(source, translation, issues, limits):
    chars = sum(int(i["extra"][0].split()[0]) for i in issues if i["kind"] == "source_script")
    if chars <= limits["max_source_script_chars"]:
        return None
    return "%d units of source-language residue left in the translation" % chars


def gate_glossary(source, translation, issues, limits):
    violations = sum(len(i["missing"]) for i in issues if i["kind"] == "glossary")
    if violations <= limits["max_glossary_violations"]:
        return None
    return "%d glossary violations" % violations


def gate_missing_segments(source, translation, issues, limits):
    missing = [i["segment"] for i in issues if i["kind"] == "missing_segment"]
    if not missing:
        return None
    return "missing segments: %s" % ", ".join(missing)


GATES = {
    "length_ratio": gate_length_ratio,
    "source_script": gate_source_script,
    "glossary": gate_glossary,
    "missing_segments": gate_missing_segments,
}


def run_gates(source, translation, issues, limits):
    """Reasons for disqualification; empty means the translation may be judged."""
    reasons = []
    for gate in GATES.values():
        reason = gate(source, translation, issues, limits)
        if reason:
            reasons.append(reason)
    return reasons


def gate_limits(cfg):
    limits = dict(DEFAULT_GATES)
    limits.update(cfg.get("gates") or {})
    return limits


# ------------------------------------------------------------ writers


def write_check(article, code, issues, reasons):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    record = {"article": article, "translator": code, "issues": issues,
              "disqualified": bool(reasons), "reasons": reasons}
    (OUT_DIR / ("mech__%s__%s.json" % (article, code))).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def print_summary(records):
    print("article  translator  issues  gate")
    for rec in records:
        status = "DISQUALIFIED: " + "; ".join(rec["reasons"]) if rec["disqualified"] else "ok"
        print("%-8s %-10s %-7d %s" % (rec["article"], rec["translator"], len(rec["issues"]), status))


# ------------------------------------------------------------ main


def main():
    cfg = load_cfg()
    RESIDUE["detector"] = RESIDUE_DETECTORS.get(cfg.get("source_lang"), count_cyrillic)
    sources = load_sources()
    if not sources:
        print("no sources; run src.convert first")
        return 1
    glossary = load_glossary(cfg)
    limits = gate_limits(cfg)
    records = []
    for (article, code), translation in load_translations().items():
        issues = check_segments(sources[article], translation, glossary)
        reasons = run_gates(sources[article], translation, issues, limits)
        records.append(write_check(article, code, issues, reasons))
    print_summary(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
