"""Aggregate judgments into data/report/summary.md.

Deterministic arithmetic only: criterion averages, Borda points from
rankings, judge agreement (Kendall tau between judges and between the two
passes of one judge), mechanical issues and gate results, latency, spend
(token estimate per model plus the OpenRouter key usage delta), and the
self-scoring check for a judge that is also a participant.

Usage: python -m src.aggregate
"""

import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import yaml

SRC_DIR = Path("data/source")
TR_DIR = Path("data/translations")
CHECK_DIR = Path("data/checks")
JUDG_DIR = Path("data/judgments")
CAL_DIR = Path("data/calibration")
REPORT_DIR = Path("data/report")
OUT = REPORT_DIR / "summary.md"
SPEND_LOG = REPORT_DIR / "spend_log.jsonl"

CRITERIA = ("meaning", "completeness", "data", "naturalness", "flow", "clean")


# ------------------------------------------------------------ loaders


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def load_json_files(folder, pattern):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob(pattern))]


def load_inputs():
    return {
        "judgments": load_json_files(JUDG_DIR, "ev__*.json"),
        "calibration": load_json_files(CAL_DIR, "cal__by__*.json"),
        "checks": load_json_files(CHECK_DIR, "mech__*.json"),
        "translations": load_json_files(TR_DIR, "tr__*__M*.json"),
        "failed_translations": load_json_files(TR_DIR, "fail__*.json"),
        "failed_judge_calls": load_json_files(JUDG_DIR, "fail__*.json") + load_json_files(CAL_DIR, "fail__*.json"),
        "sources": load_json_files(SRC_DIR, "a*.json"),
        "spend_log": [json.loads(r) for r in SPEND_LOG.read_text(encoding="utf-8").splitlines() if r.strip()]
        if SPEND_LOG.exists() else [],
    }


# ------------------------------------------------------------ logic


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def excluded_judges(calibration, judgments):
    """Judges that failed calibration, unless that would leave none."""
    failed = {c["judge"] for c in calibration if not c.get("passed", True)}
    present = {j["judge"] for j in judgments}
    relevant = failed & present
    return relevant if relevant and relevant != present else set()


def criterion_means(judgments, codes, disqualified=()):
    """Mean per criterion; a translation gated out on an article scores 0
    on that article in every judgment of it, so gating never helps."""
    scores = defaultdict(lambda: defaultdict(list))
    for judgment in judgments:
        for code in codes:
            gated = (judgment["article"], code) in disqualified
            row = None if gated else judgment["scores"].get(code)
            if row:
                for criterion in CRITERIA:
                    scores[code][criterion].append(row[criterion])
            elif gated:
                for criterion in CRITERIA:
                    scores[code][criterion].append(0)
    return {code: {c: mean(scores[code][c]) for c in CRITERIA} for code in codes}


def borda_means(judgments, codes, disqualified=()):
    """Mean Borda points; a translation gated out on an article takes 0
    points (below last place) in every judgment of that article."""
    points = defaultdict(list)
    for judgment in judgments:
        gated = [c for c in codes if (judgment["article"], c) in disqualified]
        ranking = [c for c in judgment["ranking"] if c not in gated]
        for pos, code in enumerate(ranking):
            points[code].append(len(ranking) - pos)
        for code in gated:
            points[code].append(0)
    return {code: mean(points[code]) for code in codes}


def per_judge_totals(judgments, codes):
    totals = defaultdict(lambda: defaultdict(list))
    for judgment in judgments:
        for code in codes:
            row = judgment["scores"].get(code)
            if row:
                totals[judgment["judge"]][code].append(row["total"])
    return totals


def kendall_tau(ranking_a, ranking_b):
    """Rank agreement in -1..1 over the codes both rankings contain."""
    common = [c for c in ranking_a if c in ranking_b]
    if len(common) < 2:
        return None
    pos_a = {c: i for i, c in enumerate(common)}
    pos_b = {c: ranking_b.index(c) for c in common}
    agree = disagree = 0
    for x, y in combinations(common, 2):
        same = (pos_a[x] - pos_a[y]) * (pos_b[x] - pos_b[y])
        agree, disagree = (agree + 1, disagree) if same > 0 else (agree, disagree + 1)
    return (agree - disagree) / (agree + disagree)


def judge_agreement(judgments):
    """Mean tau between every pair of judges (forward passes) per article."""
    by_article = defaultdict(dict)
    for j in judgments:
        if j.get("pass", "forward") == "forward":
            by_article[j["article"]][j["judge"]] = j["ranking"]
    taus = defaultdict(list)
    for rankings in by_article.values():
        for a, b in combinations(sorted(rankings), 2):
            tau = kendall_tau(rankings[a], rankings[b])
            if tau is not None:
                taus[(a, b)].append(tau)
    return {pair: mean(values) for pair, values in taus.items()}


def position_consistency(judgments):
    """Mean tau between a judge's forward and reverse pass; low means position bias."""
    passes = defaultdict(dict)
    for j in judgments:
        passes[(j["article"], j["judge"])][j.get("pass", "forward")] = j["ranking"]
    taus = defaultdict(list)
    for (article, judge), both in passes.items():
        if "forward" in both and "reverse" in both:
            tau = kendall_tau(both["forward"], both["reverse"])
            if tau is not None:
                taus[judge].append(tau)
    return {judge: mean(values) for judge, values in taus.items()}


def mech_summary(checks):
    issues = defaultdict(int)
    disqualified = {}
    for check in checks:
        issues[check["translator"]] += len(check["issues"])
        if check.get("disqualified"):
            disqualified[(check["article"], check["translator"])] = check["reasons"]
    return issues, disqualified


def latency_means(translations):
    by_code = defaultdict(list)
    for tr in translations:
        latency = (tr.get("usage") or {}).get("latency_sec")
        if latency is not None:
            by_code[tr["translator"]].append(latency)
    return {code: mean(values) for code, values in by_code.items()}


def usage_cost(usage, price):
    usage = usage or {}
    return (usage.get("prompt_tokens", 0) / 1e6 * price.get("input", 0)
            + usage.get("completion_tokens", 0) / 1e6 * price.get("output", 0))


def translator_costs(cfg, translations, failed):
    cost = defaultdict(float)
    for record in translations + failed:
        code = record.get("translator")
        cost[code] += usage_cost(record.get("usage"), cfg["prices"].get(code, {}))
    return cost


def judge_costs(cfg, judgments, calibration, failed_calls):
    cost = defaultdict(float)
    prices = cfg.get("judge_prices") or {}
    for record in judgments + calibration + failed_calls:
        judge = record["judge"]
        cost[judge] += usage_cost(record.get("usage"), prices.get(judge, {}))
    return cost


def actual_spend(spend_log):
    return sum(r["after"] - r["before"] for r in spend_log)


def source_words(sources):
    return sum(len(seg["text"].split()) for src in sources for seg in src["segments"])


def missing_prices(cfg):
    missing = [c for c in cfg["translators"] if c not in (cfg.get("prices") or {})]
    missing += [j for j in cfg.get("judges", {}) if j not in (cfg.get("judge_prices") or {})]
    return missing


# ------------------------------------------------------------ writers (sections)


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return lines


def section_calibration(calibration, excluded):
    if not calibration:
        return []
    rows = []
    for c in calibration:
        verdict = "pass" if c["passed"] else ("FAIL, excluded" if c["judge"] in excluded else "FAIL")
        kinds = ", ".join("%s %s" % (k, "yes" if v else "no") for k, v in (c.get("by_kind") or {}).items())
        rows.append((c["judge"], "%d/%d" % (len(c["caught"]), len(c["planted"])), c["needed"], verdict, kinds))
    lines = ["", "## Judge calibration", ""] + table(["judge", "caught", "needed", "result", "by kind"], rows)
    failed = [c for c in calibration if not c["passed"]]
    if failed and not excluded:
        lines += ["", "Warning: every judge failed calibration; nobody was excluded, read results with care."]
    return lines


def section_overall(cfg, order, means, borda, issues, latency, cost):
    header = ["model", "id"] + list(CRITERIA) + ["total/60", "borda", "mech issues", "latency s", "cost USD"]
    rows = []
    for code in order:
        row = [cfg["translators"][code], code]
        row += ["%.1f" % means[code][c] for c in CRITERIA]
        row += ["%.1f" % sum(means[code].values()), "%.2f" % borda[code], issues.get(code, 0),
                "%.1f" % latency.get(code, 0.0), "%.4f" % cost.get(code, 0.0)]
        rows.append(row)
    return ["", "## Overall", ""] + table(header, rows)


def section_disqualified(cfg, disqualified):
    if not disqualified:
        return []
    rows = [(article, code, cfg["translators"].get(code, "?"), "; ".join(reasons))
            for (article, code), reasons in sorted(disqualified.items())]
    return ["", "## Disqualified by gates (not judged)", ""] + table(["article", "id", "model", "reasons"], rows)


def section_per_judge(order, totals):
    judges = sorted(totals)
    rows = [[code] + ["%.1f" % mean(totals[j][code]) for j in judges] for code in order]
    return ["", "## Per judge (average total /60)", ""] + table(["model"] + judges, rows)


def section_agreement(agreement, consistency):
    lines = []
    if agreement:
        rows = [("%s vs %s" % pair, "%.2f" % tau) for pair, tau in sorted(agreement.items())]
        lines += ["", "## Judge agreement (Kendall tau, 1 = identical ranking)", ""] + table(["judges", "tau"], rows)
    if consistency:
        rows = [(judge, "%.2f" % tau) for judge, tau in sorted(consistency.items())]
        lines += ["", "## Position consistency (forward vs reverse pass, 1 = no position bias)", ""]
        lines += table(["judge", "tau"], rows)
    return lines


def section_self_scoring(cfg, totals, excluded):
    participants = {model: code for code, model in cfg["translators"].items()}
    self_judges = {j: participants[m] for j, m in cfg.get("judges", {}).items() if m in participants}
    if not self_judges:
        return []
    lines = ["", "## Self-scoring check", ""]
    for judge, own_code in self_judges.items():
        lines.append(_self_scoring_line(judge, own_code, totals, excluded))
    return lines


def _self_scoring_line(judge, own_code, totals, excluded):
    if judge in excluded or not totals[judge][own_code]:
        return "- %s judging its own translation %s: not counted (judge excluded)" % (judge, own_code)
    own = mean(totals[judge][own_code])
    others = [v for other in totals if other != judge for v in totals[other][own_code]]
    if not others:
        return "- %s judging its own translation %s: %.1f, no other judge to compare" % (judge, own_code, own)
    return "- %s judging its own translation %s: %.1f vs %.1f from other judges" % (judge, own_code, own, mean(others))


def section_spend(cfg, tr_cost, judge_cost, actual, missing):
    rows = [(code, cfg["translators"][code], "%.4f" % tr_cost.get(code, 0.0)) for code in cfg["translators"]]
    rows += [(judge, cfg["judges"].get(judge, "?"), "%.4f" % judge_cost[judge]) for judge in sorted(judge_cost)]
    rows.append(("total (estimate from tokens)", "", "%.4f" % (sum(tr_cost.values()) + sum(judge_cost.values()))))
    lines = ["", "## Spend USD", ""] + table(["who", "model", "cost"], rows)
    if actual is not None:
        lines += ["", "Actual spend by OpenRouter key usage: %.4f USD. It includes any other use of"
                  " the same key during the run and may lag by a few seconds; the per-model rows"
                  " above are token estimates." % actual]
    if missing:
        lines += ["", "Warning: no price in config.yaml for %s, their cost shows 0." % ", ".join(missing)]
    return lines


def section_flags(judgments):
    flags = [(j["judge"], f) for j in judgments for f in j.get("flags", [])]
    lines = ["", "## Flags (%d)" % len(flags), ""]
    for judge, f in flags:
        lines.append("- [%s] %s %s %s: %s" % (judge, f.get("translator", "?"), f.get("segment", "?"),
                                              f.get("criterion", "?"), str(f.get("quote", ""))[:160]))
    return lines


# ------------------------------------------------------------ main


def build_report(cfg, data):
    codes = list(cfg["translators"])
    excluded = excluded_judges(data["calibration"], data["judgments"])
    counted = [j for j in data["judgments"] if j["judge"] not in excluded]
    issues, disqualified = mech_summary(data["checks"])
    means = criterion_means(counted, codes, disqualified)
    borda = borda_means(counted, codes, disqualified)
    order = sorted(codes, key=lambda c: -borda[c])
    tr_cost = translator_costs(cfg, data["translations"], data["failed_translations"])
    j_cost = judge_costs(cfg, data["judgments"], data["calibration"], data["failed_judge_calls"])
    actual = actual_spend(data["spend_log"]) if data["spend_log"] else None
    lines = ["# Translation benchmark summary", "",
             "Judgments: %d (%d counted). Source size: %d words."
             % (len(data["judgments"]), len(counted), source_words(data["sources"]))]
    lines += section_calibration(data["calibration"], excluded)
    lines += section_overall(cfg, order, means, borda, issues, latency_means(data["translations"]), tr_cost)
    lines += section_disqualified(cfg, disqualified)
    lines += section_per_judge(order, per_judge_totals(counted, codes))
    lines += section_agreement(judge_agreement(data["judgments"]), position_consistency(data["judgments"]))
    lines += section_self_scoring(cfg, per_judge_totals(counted, codes), excluded)
    lines += section_spend(cfg, tr_cost, j_cost, actual, missing_prices(cfg))
    lines += section_flags(data["judgments"])
    return "\n".join(lines) + "\n"


def main():
    cfg = load_cfg()
    data = load_inputs()
    if not data["judgments"]:
        print("no judgments; run src.judge first")
        return 1
    report = build_report(cfg, data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report, encoding="utf-8")
    print("wrote %s" % OUT)
    print()
    print("\n".join(report.splitlines()[:25]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
