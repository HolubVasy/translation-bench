"""Run the whole benchmark end to end.

Usage:
  python run_all.py convert articles/1.pdf articles/2.pdf articles/3.pdf
  python run_all.py preflight [--force]
  python run_all.py translate
  python run_all.py refine
  python run_all.py check
  python run_all.py judge
  python run_all.py calibrate
  python run_all.py report
  python run_all.py assemble [--translator M4]
  python run_all.py showcase [session-id]
  python run_all.py full articles/1.pdf articles/2.pdf articles/3.pdf [--force]
"""

import sys
from datetime import datetime, timezone

from src import aggregate, assemble, calibrate, convert, judge, mech_check, preflight, refine, translate


def showcase(rest):
    """Write the public protocol to docs/data and a self-contained data/report/report.html."""
    from tools import build_report, export_session
    session_id = rest[0] if rest else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    export_session.main(session_id, "data", "docs/data")
    return build_report.main("docs/index.html", "docs/data", "data/report/report.html")


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    stage, rest = argv[0], argv[1:]
    if stage == "convert":
        return convert.main(rest)
    if stage == "preflight":
        return preflight.main(rest)
    if stage == "translate":
        return translate.main(rest)
    if stage == "refine":
        return refine.main(rest)
    if stage == "check":
        return mech_check.main()
    if stage == "judge":
        return judge.main()
    if stage == "calibrate":
        return calibrate.main()
    if stage == "report":
        return aggregate.main()
    if stage == "assemble":
        return assemble.main(rest)
    if stage == "showcase":
        return showcase(rest)
    if stage == "full":
        steps = [
            lambda: convert.main(rest),
            lambda: preflight.main([a for a in rest if a.startswith("--")]),
            lambda: translate.main([]),
            lambda: refine.main([]),
            lambda: mech_check.main(),
            lambda: judge.main(),
            lambda: calibrate.main(),
            lambda: aggregate.main(),
            lambda: assemble.main([]),
            lambda: showcase([]),
        ]
        for step in steps:
            code = step()
            if code:
                return code
        return 0
    print("unknown stage %s" % stage)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
