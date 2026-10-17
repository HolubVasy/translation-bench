"""Preflight: validate config and skills, estimate cost, write the run manifest.

Runs before any paid call. Fails fast on a broken config, a skill without
its placeholders, a glossary that does not parse, or an estimated cost
above budget.max_usd (pass --force to run anyway).

Usage: python -m src.preflight [--force]
Output: data/report/manifest.json (run id, models, skill hashes, estimate)
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from string import Template

import yaml

SRC_DIR = Path("data/source")
MANIFEST = Path("data/report/manifest.json")
SPEND_LOG = Path("data/report/spend_log.jsonl")
SKILLS = {
    "translator": {"source_lang", "target_lang", "article_json", "glossary"},
    "judge": {"source_lang", "target_lang", "n_tr", "labels", "article_id",
              "judge_code", "ranking_stub", "scores_stub", "source_json",
              "translations_block", "glossary"},
}


def load_cfg():
    return yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def load_glossary(cfg):
    """Return the glossary term list ([{ru, en: [...]}]) or [] when none."""
    path = cfg.get("glossary")
    if not path:
        return []
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    terms = data.get("terms") or []
    out = []
    for item in terms:
        src = str(item.get("source", "")).strip()
        tgt = item.get("target") or []
        if isinstance(tgt, str):
            tgt = [tgt]
        if src and tgt:
            out.append({"source": src, "target": [str(t).strip() for t in tgt]})
    return out


def validate(cfg):
    """Return a list of problems; empty means the config is sound."""
    problems = []
    translators = cfg.get("translators") or {}
    judges = cfg.get("judges") or {}
    if not translators:
        problems.append("no translators in config.yaml")
    if not judges:
        problems.append("no judges in config.yaml")
    for code in translators:
        if not re.fullmatch(r"[A-Z]+\d+", str(code)):
            problems.append("translator code %r is not like M1" % code)
    for code in judges:
        if not re.fullmatch(r"[A-Z]+\d+", str(code)):
            problems.append("judge code %r is not like J1" % code)
    if set(translators) & set(judges):
        problems.append("a code is used both as translator and judge")
    for code in translators:
        if code not in (cfg.get("prices") or {}):
            problems.append("no price for translator %s" % code)
    for code in judges:
        if code not in (cfg.get("judge_prices") or {}):
            problems.append("no judge_price for judge %s" % code)
    cal = cfg.get("calibration") or {}
    if cal.get("enabled", True):
        if cal.get("label") in translators:
            problems.append("calibration.label clashes with a translator code")
        if cal.get("base_translator") not in translators:
            problems.append("calibration.base_translator is not a translator code")
    for name, required in SKILLS.items():
        path = Path("skills") / (name + ".md")
        if not path.exists():
            problems.append("missing skills/%s.md" % name)
            continue
        found = set(Template(path.read_text(encoding="utf-8")).get_identifiers())
        missing = required - found
        if missing:
            problems.append("skills/%s.md lacks placeholders: %s" % (name, ", ".join(sorted(missing))))
        extra = found - required
        if extra:
            problems.append("skills/%s.md has unknown placeholders: %s" % (name, ", ".join(sorted(extra))))
    try:
        load_glossary(cfg)
    except Exception as err:  # noqa: BLE001
        problems.append("glossary does not load: %s" % err)
    req = cfg.get("request") or {}
    if not isinstance(req.get("max_retries"), int) or req.get("max_retries", 0) < 1:
        problems.append("request.max_retries must be an integer >= 1")
    return problems


def estimate(cfg):
    """Rough USD estimate from source size: tokens ~ chars * tokens_per_char."""
    budget = cfg.get("budget") or {}
    tpc = float(budget.get("tokens_per_char", 0.35))
    overhead = int(budget.get("prompt_overhead_tokens", 600))
    judge_out = int(budget.get("judge_output_tokens", 1500))
    sources = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SRC_DIR.glob("a*.json"))]
    chars = [sum(len(s["text"]) for s in src["segments"]) for src in sources]
    rows = []
    total = 0.0
    for code, model in (cfg.get("translators") or {}).items():
        price = cfg["prices"].get(code, {"input": 0, "output": 0})
        usd = 0.0
        for n in chars:
            tokens = n * tpc
            usd += (tokens + overhead) / 1e6 * price["input"] + tokens / 1e6 * price["output"]
        rows.append((code, model, usd))
        total += usd
    n_tr = len(cfg.get("translators") or {})
    passes = 2 if (cfg.get("judging") or {}).get("double_pass") else 1
    for code, model in (cfg.get("judges") or {}).items():
        price = (cfg.get("judge_prices") or {}).get(code, {"input": 0, "output": 0})
        usd = 0.0
        for n in chars:
            tokens = n * tpc * (1 + n_tr) + overhead
            usd += passes * (tokens / 1e6 * price["input"] + judge_out / 1e6 * price["output"])
        if (cfg.get("calibration") or {}).get("enabled", True) and chars:
            tokens = chars[0] * tpc * 2 + overhead
            usd += tokens / 1e6 * price["input"] + judge_out / 1e6 * price["output"]
        rows.append((code, model, usd))
        total += usd
    return rows, total, sum(chars)


def skill_hashes():
    out = {}
    for path in sorted(Path("skills").glob("*.md")):
        out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return out


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def write_manifest(cfg, rows, total, chars):
    import datetime

    run_id = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    manifest = {
        "run_id": run_id,
        "created": run_id,
        "git_commit": git_commit(),
        "translators": cfg.get("translators"),
        "judges": cfg.get("judges"),
        "skills": skill_hashes(),
        "config": cfg,
        "source_chars": chars,
        "estimate_usd": {code: round(usd, 4) for code, _, usd in rows},
        "estimate_total_usd": round(total, 4),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    SPEND_LOG.unlink(missing_ok=True)  # a run starts here; the key span covers this run only
    return run_id


def main(argv=None):
    argv = argv or []
    cfg = load_cfg()
    problems = validate(cfg)
    if problems:
        print("preflight FAILED:")
        for item in problems:
            print("  - " + item)
        return 1
    rows, total, chars = estimate(cfg)
    print("source: %d chars in %d article(s)" % (chars, len(list(SRC_DIR.glob("a*.json")))))
    print("estimated spend USD (rough, from source size):")
    for code, model, usd in rows:
        print("  %-4s %-32s %.4f" % (code, model, usd))
    print("  total %.4f" % total)
    run_id = write_manifest(cfg, rows, total, chars)
    print("manifest: %s (run %s)" % (MANIFEST, run_id))
    max_usd = (cfg.get("budget") or {}).get("max_usd")
    if max_usd is not None and total > float(max_usd) and "--force" not in argv:
        print("estimate %.4f exceeds budget.max_usd %.2f; pass --force to run anyway" % (total, float(max_usd)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
