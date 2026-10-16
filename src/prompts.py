"""Prompt builders. The prompt texts themselves live in skills/*.md
as string.Template files ($placeholders), editable without touching code."""

from pathlib import Path
from string import Template

SKILLS_DIR = Path("skills")

SCORE_LINE = '    "{code}": {{"meaning": 0, "completeness": 0, "data": 0, "naturalness": 0, "flow": 0, "clean": 0, "total": 0}}'


def load_skill(name):
    return Template((SKILLS_DIR / (name + ".md")).read_text(encoding="utf-8"))


def build_translator_prompt(cfg, article_json_str):
    return load_skill("translator").substitute(
        source_lang=cfg["source_lang"],
        target_lang=cfg["target_lang"],
        article_json=article_json_str,
    )


def build_judge_prompt(cfg, article_id, judge_code, source_json_str, translations):
    """translations: list of (code, json_str) in the already shuffled order."""
    labels = ", ".join(code for code, _ in translations)
    blocks = []
    for code, body in translations:
        blocks.append("TRANSLATION %s:\n%s" % (code, body))
    scores_stub = ",\n".join(SCORE_LINE.format(code=code) for code, _ in translations)
    ranking_stub = ", ".join('"..."' for _ in translations)
    return load_skill("judge").substitute(
        source_lang=cfg["source_lang"],
        target_lang=cfg["target_lang"],
        n_tr=len(translations),
        labels=labels,
        article_id=article_id,
        judge_code=judge_code,
        ranking_stub=ranking_stub,
        scores_stub=scores_stub,
        source_json=source_json_str,
        translations_block="\n\n".join(blocks),
    )
