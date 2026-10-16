"""Convert .docx articles to segmented JSON.

Segment ids are structural addresses: S2-p3 means section 2, paragraph 3.
Headings are S2-h (or S2-h2 for a second heading inside the section),
images are S2-img1. A new section starts at every Heading 1 paragraph.
Images are replaced by [IMAGE_n] placeholders; the originals stay in the docx.

Usage: python -m src.convert articles/1.docx [more .docx ...]
Output: data/source/a{n}.json (n taken from the file name if it is a number,
otherwise sequential).
"""

import json
import re
import sys
from pathlib import Path

from docx import Document

SRC_DIR = Path("data/source")

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING_TAGS = (W_NS + "drawing", W_NS + "object", W_NS + "pict")


def para_has_image(paragraph):
    for run in paragraph.runs:
        for tag in DRAWING_TAGS:
            if run._element.find(tag) is not None:
                return True
    return False


def heading_level(paragraph):
    name = (paragraph.style.name or "").lower()
    match = re.match(r"heading\s+(\d+)", name)
    if match:
        return int(match.group(1))
    if name in ("title", "zagolovok"):
        return 1
    return 0


def convert_docx(path, article_id):
    doc = Document(str(path))
    segments = []
    section = 0
    p_count = 0
    h_count = 0
    img_total = 0
    img_in_section = 0

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        has_image = para_has_image(paragraph)
        if not text and not has_image:
            continue

        level = heading_level(paragraph)
        if level == 1 or section == 0:
            section += 1
            p_count = 0
            h_count = 0
            img_in_section = 0

        if has_image:
            img_total += 1
            img_in_section += 1
            segments.append(
                {
                    "id": "S%d-img%d" % (section, img_in_section),
                    "section": section,
                    "type": "image",
                    "text": "[IMAGE_%d]" % img_total,
                }
            )
            if not text:
                continue

        if level > 0:
            h_count += 1
            seg_id = "S%d-h" % section if h_count == 1 else "S%d-h%d" % (section, h_count)
            seg_type = "h%d" % level
        else:
            p_count += 1
            seg_id = "S%d-p%d" % (section, p_count)
            seg_type = "p"

        segments.append(
            {"id": seg_id, "section": section, "type": seg_type, "text": text}
        )

    return {"article": str(article_id), "segments": segments}


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    next_seq = 1
    for raw in argv:
        path = Path(raw)
        stem_digits = re.sub(r"\D", "", path.stem)
        if stem_digits:
            article_id = int(stem_digits)
        else:
            article_id = next_seq
        next_seq = article_id + 1
        data = convert_docx(path, article_id)
        out = SRC_DIR / ("a%s.json" % article_id)
        out.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            "%s -> %s (%d segments, %d sections)"
            % (
                path.name,
                out,
                len(data["segments"]),
                data["segments"][-1]["section"] if data["segments"] else 0,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
