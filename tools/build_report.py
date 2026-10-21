"""Build a self-contained report.html from the showcase page and the latest session.

The result opens with a double click, no server and no network needed for the data.
Usage: python tools/build_report.py [template] [data-dir] [out-file]
"""
import json
import sys
from pathlib import Path

MARK = "<script>\n\"use strict\";"


def load_latest(data_dir):
    sessions = Path(data_dir) / "sessions"
    index = json.loads((sessions / "index.json").read_text())
    folder = sessions / index["latest"]
    return {
        "index": index,
        "session": json.loads((folder / "session.json").read_text()),
        "verdicts": json.loads((folder / "verdicts.json").read_text()),
    }


def main(template="docs/index.html", data_dir="docs/data", out_file="data/report/report.html"):
    page = Path(template).read_text()
    if MARK not in page:
        print("template has no script marker, report not built")
        return 1
    embed = "<script>window.TB_EMBED = " + json.dumps(load_latest(data_dir), ensure_ascii=True) + ";</script>\n"
    out = Path(out_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page.replace(MARK, embed + MARK, 1))
    print("report:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
