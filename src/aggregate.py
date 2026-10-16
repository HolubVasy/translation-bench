"""Aggregate judgments into data/report/summary.md.

Deterministic arithmetic only: average scores per criterion, Borda points
from rankings, mechanical check issue counts, cost per 1K source words,
and a separate view of the judge that is also a participant (self-scoring).

Usage: python -m src.aggregate
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
CHECK_DIR = Path("data/checks")
JUDG_DIR = Path("data/judgments")
CAL_DIR = Path("data/calibration")
OUT = Path("data/report/summary.md")

CRITERIA = ("meaning", "completeness", "data", "naturalness", "flow", "clean")


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def main():
    cfg = load_cfg()
    codes = list(cfg["translators"])
    judgments = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(JUDG_DIR.glob("ev__*.json"))
    ]
    if not judgments:
        print("no judgments; run src.judge first")
        return 1

    calibration = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(CAL_DIR.glob("cal__by__*.json"))
    ]
    failed = {c["judge"] for c in calibration if not c.get("passed", True)}
    all_judges = {j["judge"] for j in judgments}
    excluded = failed if failed and failed != all_judges else set()
    all_judgments = judgments
    judgments = [j for j in judgments if j["judge"] not in excluded]

    # Which judge model is also a participant (same OpenRouter id).
    participant_models = {model: code for code, model in cfg["translators"].items()}
    self_judges = {
        j_code: participant_models[model]
        for j_code, model in cfg["judges"].items()
        if model in participant_models
    }

    scores = defaultdict(lambda: defaultdict(list))  # code -> criterion -> values
    borda = defaultdict(list)  # code -> points per round
    per_judge_total = defaultdict(lambda: defaultdict(list))  # judge -> code -> totals
    flags = []
    n = len(codes)

    for judgment in judgments:
        judge = judgment["judge"]
        for code in codes:
            row = judgment["scores"][code]
            for criterion in CRITERIA:
                scores[code][criterion].append(row[criterion])
            per_judge_total[judge][code].append(row["total"])
        for pos, code in enumerate(judgment["ranking"]):
            borda[code].append(n - pos)
        for flag in judgment.get("flags", []):
            flag["judge"] = judge
            flags.append(flag)

    mech_issues = defaultdict(int)
    for check_path in CHECK_DIR.glob("mech__*.json"):
        data = json.loads(check_path.read_text(encoding="utf-8"))
        mech_issues[data["translator"]] += len(data["issues"])

    # Source size for the cost estimate.
    total_words = 0
    for src_path in SRC_DIR.glob("a*.json"):
        data = json.loads(src_path.read_text(encoding="utf-8"))
        total_words += sum(len(seg["text"].split()) for seg in data["segments"])

    cost = {}
    for tr_path in TR_DIR.glob("tr__*__M*.json"):
        data = json.loads(tr_path.read_text(encoding="utf-8"))
        code = data.get("translator")
        usage = data.get("usage") or {}
        price = cfg["prices"].get(code, {"input": 0, "output": 0})
        dollars = (
            usage.get("prompt_tokens", 0) / 1e6 * price["input"]
            + usage.get("completion_tokens", 0) / 1e6 * price["output"]
        )
        cost[code] = cost.get(code, 0.0) + dollars

    lines = []
    lines.append("# Translation benchmark summary")
    lines.append("")
    lines.append("Judgments: %d. Source size: %d words." % (len(judgments), total_words))
    if calibration:
        lines.append("")
        lines.append("## Judge calibration")
        lines.append("")
        lines.append("| judge | caught | needed | result |")
        lines.append("|---|---|---|---|")
        for c in calibration:
            lines.append("| %s | %d/%d | %d | %s |" % (
                c["judge"], len(c["caught"]), len(c["planted"]), c["needed"],
                "pass" if c["passed"] else "FAIL, excluded" if c["judge"] in excluded else "FAIL"))
        if failed and not excluded:
            lines.append("")
            lines.append("Warning: every judge failed calibration; nobody was excluded, read results with care.")
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    header = ["model", "id"] + list(CRITERIA) + ["total/60", "borda", "mech issues", "cost USD"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    order = sorted(codes, key=lambda c: -mean(borda[c]))
    for code in order:
        row = [cfg["translators"][code], code]
        total = 0.0
        for criterion in CRITERIA:
            value = mean(scores[code][criterion])
            total += value
            row.append("%.1f" % value)
        row.append("%.1f" % total)
        row.append("%.2f" % mean(borda[code]))
        row.append(str(mech_issues.get(code, 0)))
        row.append("%.4f" % cost.get(code, 0.0))
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("## Per judge (average total /60)")
    lines.append("")
    judge_names = sorted(per_judge_total)
    lines.append("| model | " + " | ".join(judge_names) + " |")
    lines.append("|" + "---|" * (len(judge_names) + 1))
    for code in order:
        row = [code]
        for judge in judge_names:
            row.append("%.1f" % mean(per_judge_total[judge][code]))
        lines.append("| " + " | ".join(row) + " |")

    if self_judges:
        lines.append("")
        lines.append("## Self-scoring check")
        lines.append("")
        for judge, own_code in self_judges.items():
            own = mean(per_judge_total[judge][own_code])
            others = mean(
                value
                for other_judge in judge_names
                if other_judge != judge
                for value in per_judge_total[other_judge][own_code]
            )
            lines.append(
                "- %s judging its own translation %s: %.1f vs %.1f from other judges"
                % (judge, own_code, own, others)
            )

    judge_cost = defaultdict(float)
    judge_prices = cfg.get("judge_prices", {})
    for judgment in all_judgments + [c for c in calibration]:
        judge = judgment["judge"]
        usage = judgment.get("usage") or {}
        price = judge_prices.get(judge, {"input": 0, "output": 0})
        judge_cost[judge] += (
            usage.get("prompt_tokens", 0) / 1e6 * price["input"]
            + usage.get("completion_tokens", 0) / 1e6 * price["output"]
        )
    lines.append("")
    lines.append("## Spend USD")
    lines.append("")
    lines.append("| who | model | cost |")
    lines.append("|---|---|---|")
    for code in codes:
        lines.append("| %s | %s | %.4f |" % (code, cfg["translators"][code], cost.get(code, 0.0)))
    for judge in sorted(judge_cost):
        lines.append("| %s | %s | %.4f |" % (judge, cfg["judges"].get(judge, "?"), judge_cost[judge]))
    total_spend = sum(cost.values()) + sum(judge_cost.values())
    lines.append("| total | | %.4f |" % total_spend)
    missing_prices = [c for c in codes if c not in cfg.get("prices", {})]
    if missing_prices:
        lines.append("")
        lines.append("Warning: no price in config.yaml for %s, their cost shows 0." % ", ".join(missing_prices))

    lines.append("")
    lines.append("## Flags (%d)" % len(flags))
    lines.append("")
    for flag in flags:
        lines.append(
            "- [%s] %s %s %s: %s"
            % (
                flag.get("judge", "?"),
                flag.get("translator", "?"),
                flag.get("segment", "?"),
                flag.get("criterion", "?"),
                str(flag.get("quote", ""))[:160],
            )
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote %s" % OUT)
    print()
    print("\n".join(lines[:20]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
