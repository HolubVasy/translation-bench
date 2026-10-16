"""Convert source articles (.pdf or .docx) to segmented JSON.

Segment ids are structural addresses: S2-p3 means section 2, paragraph 3.
Headings are S2-h (or S2-h2 for a second heading inside the section),
images are S2-img1. A new section starts at every level-1 heading.
Images become [IMAGE_n] placeholders. For PDF input the image regions are
also saved to data/source/images/a{n}/IMAGE_{n}.png so the winning
translation can be assembled back into a document (src.assemble).

PDF has no styles, so structure is recovered from layout:
- body font size = character-weighted median of all text blocks;
- a short block clearly larger than body is a heading, the largest
  heading size is level 1, any smaller heading size is level 2;
- blocks repeated in the top or bottom margin of several pages
  (running headers, footers) and bare page numbers are dropped;
- lines are joined with spaces, words hyphenated across lines are glued.
Review data/source/a{n}.json once before a paid run.

Usage: python -m src.convert articles/1.pdf [more files ...]
Output: data/source/a{n}.json (n from the digits in the file name,
otherwise sequential).
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

SRC_DIR = Path("data/source")
IMG_ROOT = SRC_DIR / "images"

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING_TAGS = (W_NS + "drawing", W_NS + "object", W_NS + "pict")

MARGIN_FRACTION = 0.08
HEADING_RATIO_MIN = 1.15
HEADING_MAX_CHARS = 200
MIN_IMAGE_SIDE = 50
SOFT_HYPHEN = "\u00ad"


# ---------------------------------------------------------------- segments


def build_segments(items):
    """items: dicts with kind in (heading, para, image), level for headings.
    Returns the flat segment list with structural ids."""
    segments = []
    section = 0
    p_count = h_count = img_in_section = img_total = 0
    for item in items:
        kind = item["kind"]
        level = item.get("level", 0)
        if (kind == "heading" and level == 1) or section == 0:
            section += 1
            p_count = h_count = img_in_section = 0
        if kind == "image":
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
            item["image_number"] = img_total
        elif kind == "heading":
            h_count += 1
            seg_id = "S%d-h" % section if h_count == 1 else "S%d-h%d" % (section, h_count)
            segments.append(
                {"id": seg_id, "section": section, "type": "h%d" % level, "text": item["text"]}
            )
        else:
            p_count += 1
            segments.append(
                {"id": "S%d-p%d" % (section, p_count), "section": section,
                 "type": "p", "text": item["text"]}
            )
    return segments


# ---------------------------------------------------------------- docx


def _para_has_image(paragraph):
    for run in paragraph.runs:
        for tag in DRAWING_TAGS:
            if run._element.find(tag) is not None:
                return True
    return False


def _docx_heading_level(paragraph):
    name = (paragraph.style.name or "").lower()
    match = re.match(r"heading\s+(\d+)", name)
    if match:
        return int(match.group(1))
    if name == "title":
        return 1
    return 0


def docx_items(path):
    from docx import Document

    items = []
    for paragraph in Document(str(path)).paragraphs:
        text = paragraph.text.strip()
        has_image = _para_has_image(paragraph)
        if not text and not has_image:
            continue
        level = _docx_heading_level(paragraph)
        if has_image:
            items.append({"kind": "image"})
            if not text:
                continue
        if level > 0:
            items.append({"kind": "heading", "level": level, "text": text})
        else:
            items.append({"kind": "para", "text": text})
    return items


# ---------------------------------------------------------------- pdf


def join_lines(lines):
    text = ""
    for line in lines:
        line = line.replace(SOFT_HYPHEN, "").strip()
        if not line:
            continue
        if not text:
            text = line
        elif text.endswith("-") and line[:1].islower():
            text = text[:-1] + line
        else:
            text = text + " " + line
    return re.sub(r"\s+", " ", text).strip()


def _weighted_median(pairs):
    """pairs: (value, weight)."""
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    acc = 0
    for value, weight in pairs:
        acc += weight
        if acc >= total / 2:
            return value
    return pairs[-1][0] if pairs else 0


def _norm_repeat(text):
    return re.sub(r"\d+", "#", text).strip().lower()


def pdf_raw_blocks(path):
    import pymupdf

    doc = pymupdf.open(str(path))
    blocks = []
    for pno, page in enumerate(doc):
        height = page.rect.height
        for block in page.get_text("dict")["blocks"]:
            x0, y0, x1, y1 = block["bbox"]
            in_margin = y1 < height * MARGIN_FRACTION or y0 > height * (1 - MARGIN_FRACTION)
            if block["type"] == 1:
                if (x1 - x0) < MIN_IMAGE_SIDE or (y1 - y0) < MIN_IMAGE_SIDE:
                    continue
                blocks.append({"page": pno, "kind": "image", "bbox": block["bbox"]})
                continue
            lines, sizes = [], []
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"])
                if text.strip():
                    lines.append(text)
                    sizes += [span["size"] for span in line["spans"] if span["text"].strip()]
            text = join_lines(lines)
            if not text:
                continue
            blocks.append(
                {"page": pno, "kind": "text", "text": text, "size": max(sizes),
                 "margin": in_margin}
            )
    return doc, blocks


def pdf_items(path, img_dir):
    doc, blocks = pdf_raw_blocks(path)
    n_pages = len(doc)

    # Running headers and footers: same normalized text in the margin of
    # several pages. Bare page numbers in the margin always go.
    margin_counts = Counter(
        _norm_repeat(b["text"]) for b in blocks if b["kind"] == "text" and b["margin"]
    )
    repeat_min = max(2, int(n_pages * 0.3))

    def is_furniture(block):
        if not block["margin"]:
            return False
        if re.fullmatch(r"[\d\s\-/|.]+", block["text"]):
            return True
        return n_pages > 1 and margin_counts[_norm_repeat(block["text"])] >= repeat_min

    texts = [b for b in blocks if b["kind"] == "text" and not is_furniture(b)]
    body = _weighted_median([(round(b["size"], 1), len(b["text"])) for b in texts]) or 10

    heading_sizes = sorted(
        {round(b["size"], 1) for b in texts
         if b["size"] >= body * HEADING_RATIO_MIN and len(b["text"]) <= HEADING_MAX_CHARS},
        reverse=True,
    )
    top_heading = heading_sizes[0] if heading_sizes else None

    items = []
    image_blocks = []
    for block in blocks:
        if block["kind"] == "image":
            items.append({"kind": "image"})
            image_blocks.append((items[-1], block))
            continue
        if is_furniture(block):
            continue
        size = round(block["size"], 1)
        if top_heading and size in heading_sizes:
            level = 1 if size == top_heading else 2
            items.append({"kind": "heading", "level": level, "text": block["text"]})
        else:
            items.append({"kind": "para", "text": block["text"]})

    return doc, items, image_blocks


def save_pdf_images(doc, image_blocks, img_dir):
    import pymupdf

    img_dir.mkdir(parents=True, exist_ok=True)
    for old in img_dir.glob("IMAGE_*"):
        old.unlink()
    for item, block in image_blocks:
        page = doc[block["page"]]
        pix = page.get_pixmap(clip=pymupdf.Rect(block["bbox"]), dpi=150)
        pix.save(str(img_dir / ("IMAGE_%d.png" % item["image_number"])))


# ---------------------------------------------------------------- main


def convert_file(path, article_id):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        img_dir = IMG_ROOT / ("a%s" % article_id)
        doc, items, image_blocks = pdf_items(path, img_dir)
        segments = build_segments(items)
        save_pdf_images(doc, image_blocks, img_dir)
    elif suffix == ".docx":
        segments = build_segments(docx_items(path))
    else:
        raise ValueError("unsupported input %s (use .pdf or .docx)" % path.name)
    return {"article": str(article_id), "segments": segments}


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    next_seq = 1
    for raw in argv:
        path = Path(raw)
        digits = re.sub(r"\D", "", path.stem)
        article_id = int(digits) if digits else next_seq
        next_seq = article_id + 1
        data = convert_file(path, article_id)
        out = SRC_DIR / ("a%s.json" % article_id)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        segs = data["segments"]
        print(
            "%s -> %s (%d segments, %d sections, %d images)"
            % (path.name, out, len(segs), segs[-1]["section"] if segs else 0,
               sum(1 for s in segs if s["type"] == "image"))
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
