"""Offline smoke test of the whole pipeline. No API calls.

Builds a synthetic PDF (title, two sections, an image, running header and
page numbers), converts it, fakes translations and judgments, plants a
decoy and scores a fake calibration, then runs check, report and assemble.
Runs in a temporary directory, so the repository stays clean.

Usage: python tests/smoke.py
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

FAILS = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def make_pdf(path):
    import pymupdf

    doc = pymupdf.open()
    paras = [
        "The first paragraph is about 25 percent of the market and it is growing fast. "
        "Another sentence follows here.",
        "The second paragraph has a link https://example.com/page and the value 1,5. "
        "It does not mention anything else.",
    ]
    for pno in range(2):
        page = doc.new_page()
        page.insert_text((72, 30), "Company Report Header", fontsize=8)
        page.insert_text((300, 820), str(pno + 1), fontsize=8)
        y = 90
        title = "Introduction" if pno == 0 else "Conclusion"
        page.insert_textbox(pymupdf.Rect(72, y, 520, y + 40), title, fontsize=22)
        y += 60
        for text in paras:
            page.insert_textbox(pymupdf.Rect(72, y, 520, y + 70), text, fontsize=11)
            y += 90
        if pno == 0:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 120), 0)
            pix.clear_with(180)
            page.insert_image(pymupdf.Rect(72, y, 192, y + 120), pixmap=pix)
    doc.save(str(path))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="tbench-smoke-"))
    try:
        shutil.copy(REPO / "config.yaml", tmp / "config.yaml")
        shutil.copytree(REPO / "skills", tmp / "skills")
        os.chdir(tmp)
        from src import aggregate, assemble, calibrate, convert, mech_check

        make_pdf(tmp / "1.pdf")
        check(convert.main([str(tmp / "1.pdf")]) == 0, "convert pdf")
        src = json.loads(Path("data/source/a1.json").read_text(encoding="utf-8"))
        segs = src["segments"]
        ids = [s["id"] for s in segs]
        texts = " ".join(s["text"] for s in segs)
        check("S1-h" in ids and "S2-h" in ids, "two sections from headings: %s" % ids)
        check(any(s["type"] == "image" for s in segs), "image segment present")
        check("Company Report Header" not in texts, "running header removed")
        check(not any(s["text"].strip() in ("1", "2") for s in segs), "page numbers removed")
        check(Path("data/source/images/a1/IMAGE_1.png").exists(), "image saved")

        cfg = calibrate.load_cfg()
        codes = list(cfg["translators"])
        Path("data/translations").mkdir(parents=True, exist_ok=True)
        for code in codes:
            tr = {"article": "1", "segments": segs, "translator": code,
                  "usage": {"prompt_tokens": 1000, "completion_tokens": 800}}
            if code == codes[-1]:
                tr = json.loads(json.dumps(tr))
                tr["segments"][1]["text"] = tr["segments"][1]["text"].replace("25", "52")
            Path("data/translations/tr__a1__%s.json" % code).write_text(json.dumps(tr))
        check(mech_check.main() == 0, "mech check runs")
        mech = json.loads(Path("data/checks/mech__a1__%s.json" % codes[-1]).read_text())
        check(len(mech["issues"]) >= 1, "mech check catches the broken number")

        Path("data/judgments").mkdir(parents=True, exist_ok=True)
        for j in cfg["judges"]:
            scores = {c: {"meaning": 8, "completeness": 9, "data": 9, "naturalness": 7,
                          "flow": 8, "clean": 10, "total": 51} for c in codes}
            Path("data/judgments/ev__a1__by__%s.json" % j).write_text(json.dumps(
                {"protocol": "evaluation", "article": "a1", "judge": j,
                 "ranking": codes, "scores": scores, "flags": [], "verdict": "t",
                 "usage": {"prompt_tokens": 9000, "completion_tokens": 700}}))

        base = json.loads(Path("data/translations/tr__a1__%s.json" % codes[0]).read_text())
        decoy, planted = calibrate.make_decoy(calibrate.strip_for_judge(base))
        check(len(planted) == 3, "three errors planted: %s" % [p["kind"] for p in planted])
        check(len({p["segment"] for p in planted}) == len(planted), "planted in distinct segments")
        calibrate.write_answer_key("a1", codes[0], "M6", planted)
        check(Path("data/calibration/decoy__a1.md").exists(), "answer key written")

        judges = list(cfg["judges"])
        for i, j in enumerate(judges):
            flagged = planted if i == 0 else planted[:1]
            fake = {"flags": [{"translator": "M6", "segment": p["segment"]} for p in flagged]}
            caught = calibrate.score_catches(fake, planted, "M6")
            Path("data/calibration/cal__by__%s.json" % j).write_text(json.dumps(
                {"judge": j, "article": "a1", "label": "M6",
                 "planted": [p["segment"] for p in planted], "caught": caught,
                 "needed": 2, "passed": len(caught) >= 2, "usage": {}}))
        Path("data/translations/fail__a1__%s.json" % codes[0]).write_text(json.dumps(
            {"article": "a1", "translator": codes[0], "error": "x",
             "usage": {"prompt_tokens": 1000000, "completion_tokens": 0}}))
        Path("data/report").mkdir(parents=True, exist_ok=True)
        Path("data/report/spend_log.jsonl").write_text(
            json.dumps({"stage": "translate", "before": 10.0, "after": 10.25}) + "\n"
            + json.dumps({"stage": "judge", "before": 10.25, "after": 11.0}) + "\n")
        check(aggregate.main() == 0, "report builds")
        report = Path("data/report/summary.md").read_text()
        check("## Judge calibration" in report and "FAIL, excluded" in report,
              "calibration section and exclusion shown")
        check("## Spend USD" in report, "spend section present")
        check("Actual spend by OpenRouter key usage: 1.0000 USD" in report, "actual spend from key usage delta")
        price_in = cfg["prices"][codes[0]]["input"]
        check("| %s | %s | %.4f |" % (codes[0], cfg["translators"][codes[0]], 0.0013 + price_in) in report
              or price_in == 0, "failed but billed attempts counted in spend")
        check("not counted (judge excluded)" in report,
              "excluded self-judge is not shown as a 0.0 score")
        from src.openrouter import add_usage
        spent = {}
        add_usage(spent, {"prompt_tokens": 10, "completion_tokens": 5})
        add_usage(spent, {"prompt_tokens": 7})
        check(spent == {"prompt_tokens": 17, "completion_tokens": 5},
              "usage accumulates across attempts")

        check(assemble.main(["--translator", codes[0]]) == 0, "assemble runs")
        tie_dir = Path("data/judgments")
        saved = {f: f.read_text() for f in tie_dir.glob("ev__*.json")}
        for i, f in enumerate(sorted(saved)):
            data = json.loads(saved[f])
            pair = [codes[1], codes[0]] if i % 2 == 0 else [codes[0], codes[1]]
            data["ranking"] = pair + [c for c in codes if c not in pair]
            f.write_text(json.dumps(data))
        for f in Path("data/calibration").glob("cal__by__*.json"):
            f.rename(f.with_suffix(".bak"))
        keep = sorted(saved)[:2]
        for f in sorted(saved)[2:]:
            f.rename(f.with_suffix(".bak"))
        check(assemble.borda_winner() == codes[0], "Borda tie goes to the first code in config")
        for f in tie_dir.glob("*.bak"):
            f.rename(f.with_suffix(".json"))
        for f in Path("data/calibration").glob("*.bak"):
            f.rename(f.with_suffix(".json"))
        for f, text in saved.items():
            f.write_text(text)
        winner = assemble.borda_winner()
        check(winner == codes[0], "assemble winner follows only passing judges: %s" % winner)
        from docx import Document
        out = Document("data/report/assembled__a1__%s.docx" % codes[0])
        check(len(out.inline_shapes) == 1, "assembled docx contains the image")
    finally:
        os.chdir(REPO)
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("SMOKE FAILED: %d" % len(FAILS) if FAILS else "SMOKE PASSED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
