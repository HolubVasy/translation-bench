"""Deterministic checks: numbers, URLs and placeholders per segment.

Usage: python -m src.mech_check
Reads data/source and data/translations, writes data/checks/mech__a{n}__{code}.json
and prints a summary. These cover the "data" criterion mechanically; judges
still cover meaning and language.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
OUT_DIR = Path("data/checks")

NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
URL_RE = re.compile(r"https?://[^\s\)\]\>\"']+")
PLACEHOLDER_RE = re.compile(r"\[IMAGE_\d+\]")


def normalize_number(num):
    # 1,5 and 1.5 are the same value written in two locales.
    return num.replace(",", ".")


def tokens(text, pattern, normalizer=None):
    found = pattern.findall(text)
    if normalizer:
        found = [normalizer(item) for item in found]
    return Counter(found)


def check_pair(source, translation):
    issues = []
    tr_by_id = {seg["id"]: seg for seg in translation["segments"]}
    for src_seg in source["segments"]:
        out_seg = tr_by_id.get(src_seg["id"])
        if out_seg is None:
            issues.append({"segment": src_seg["id"], "kind": "missing_segment"})
            continue
        for kind, pattern, norm in (
            ("numbers", NUM_RE, normalize_number),
            ("urls", URL_RE, None),
            ("placeholders", PLACEHOLDER_RE, None),
        ):
            src_tokens = tokens(src_seg["text"], pattern, norm)
            out_tokens = tokens(out_seg["text"], pattern, norm)
            missing = src_tokens - out_tokens
            extra = out_tokens - src_tokens
            if missing or extra:
                issues.append(
                    {
                        "segment": src_seg["id"],
                        "kind": kind,
                        "missing": sorted(missing.elements()),
                        "extra": sorted(extra.elements()),
                    }
                )
    return issues


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in SRC_DIR.glob("a*.json")}
    if not sources:
        print("no sources; run src.convert first")
        return 1
    rows = []
    for tr_path in sorted(TR_DIR.glob("tr__a*__M*.json")):
        _, article, code = tr_path.stem.split("__")
        translation = json.loads(tr_path.read_text(encoding="utf-8"))
        issues = check_pair(sources[article], translation)
        out = OUT_DIR / ("mech__%s__%s.json" % (article, code))
        out.write_text(
            json.dumps({"article": article, "translator": code, "issues": issues},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rows.append((article, code, len(issues)))
    print("article  translator  issues")
    for article, code, count in rows:
        print("%-8s %-10s %d" % (article, code, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
