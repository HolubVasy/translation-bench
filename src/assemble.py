"""Assemble a translation back into a .docx document.

Headings and paragraphs come from the translated segments; [IMAGE_n]
placeholders are replaced by the images saved at convert time
(data/source/images/a{n}/IMAGE_{n}.png, PDF input only). A placeholder
without an image file stays as text.

The translator defaults to the overall winner by Borda points, computed
exactly as in the report (same exclusions, same tie-break); pass
--translator to choose another one.

Usage: python -m src.assemble [--translator M4] [a1 a2 ...]
Output: data/report/assembled__a{n}__M{k}.docx
"""

import argparse
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Inches

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
JUDG_DIR = Path("data/judgments")
CHECK_DIR = Path("data/checks")
CAL_DIR = Path("data/calibration")
OUT_DIR = Path("data/report")


def borda_winner():
    """Overall winner by Borda, same exclusions and tie-break as the report."""
    from .aggregate import borda_means, excluded_judges, load_json_files, mech_summary

    import yaml
    cfg = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    judgments = load_json_files(JUDG_DIR, "ev__*.json")
    if not judgments:
        return None
    excluded = excluded_judges(load_json_files(CAL_DIR, "cal__by__*.json"), judgments)
    counted = [j for j in judgments if j["judge"] not in excluded]
    codes = list(cfg["translators"])
    _, disqualified = mech_summary(load_json_files(CHECK_DIR, "mech__*.json"))
    borda = borda_means(counted, codes, disqualified)
    return sorted(codes, key=lambda c: -borda[c])[0]


def assemble(article, code):
    tr_path = TR_DIR / ("tr__%s__%s.json" % (article, code))
    if not tr_path.exists():
        print("missing %s" % tr_path)
        return None
    translation = json.loads(tr_path.read_text(encoding="utf-8"))
    img_dir = SRC_DIR / "images" / article
    doc = Document()
    for seg in translation["segments"]:
        kind, text = seg["type"], seg["text"]
        if kind == "image":
            match = re.search(r"\[IMAGE_(\d+)\]", text)
            img = img_dir / ("IMAGE_%s.png" % match.group(1)) if match else None
            if img and img.exists():
                doc.add_picture(str(img), width=Inches(6))
            else:
                doc.add_paragraph(text)
        elif kind.startswith("h"):
            level = int(kind[1:]) if kind[1:].isdigit() else 1
            doc.add_heading(text, level=min(level, 4))
        else:
            doc.add_paragraph(text)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ("assembled__%s__%s.docx" % (article, code))
    doc.save(str(out))
    return out


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--translator")
    parser.add_argument("articles", nargs="*")
    args = parser.parse_args(argv)
    code = args.translator or borda_winner()
    if not code:
        print("no judgments yet; pass --translator explicitly")
        return 1
    articles = args.articles or sorted(p.stem for p in SRC_DIR.glob("a*.json"))
    built = 0
    for article in articles:
        out = assemble(article, code)
        if out:
            built += 1
            print("assembled %s" % out)
    return 0 if built else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
