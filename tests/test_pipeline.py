"""Unit tests for judge validation, ordering, calibration planters and aggregation."""

from src.aggregate import (borda_means, criterion_means, excluded_judges, judge_agreement,
                           kendall_tau, position_consistency)
from src.calibrate import caught_by_kind, make_decoy, score_catches
from src.judge import CRITERIA, presentation_order, validate_judgment
from src.preflight import validate

CODES = ["M1", "M2", "M3"]


def judgment(judge, ranking, pass_name="forward", flags=()):
    scores = {c: {k: 8 for k in CRITERIA} for c in ranking}
    for row in scores.values():
        row["total"] = sum(row[k] for k in CRITERIA)
    return {"judge": judge, "article": "a1", "pass": pass_name, "ranking": list(ranking),
            "scores": scores, "flags": list(flags)}


# ---------------------------------------------------------------- judge


def test_validate_judgment_accepts_complete_and_rejects_partial():
    good = judgment("J1", CODES)
    assert validate_judgment(good, CODES) == []
    assert good["scores"]["M1"]["total"] == 48
    bad = judgment("J1", ["M1", "M2"])
    errors = validate_judgment(bad, CODES)
    assert any("permutation" in e for e in errors) and any("M3" in e for e in errors)
    out_of_range = judgment("J1", CODES)
    out_of_range["scores"]["M2"]["meaning"] = 11
    assert validate_judgment(out_of_range, CODES) == ["M2.meaning out of range"]


def test_presentation_order_is_seeded_and_reverse_mirrors_forward():
    forward = presentation_order(CODES, "a1", "J1", "forward")
    assert sorted(forward) == CODES
    assert presentation_order(CODES, "a1", "J1", "forward") == forward
    assert presentation_order(CODES, "a1", "J1", "reverse") == forward[::-1]
    assert presentation_order(CODES, "a1", "J2", "forward") != forward or len(CODES) < 3


# ---------------------------------------------------------------- calibration


def test_make_decoy_plants_each_kind_in_a_distinct_paragraph():
    translation = {"article": "1", "segments": [
        {"id": "S1-p1", "section": 1, "type": "p", "text": "The rate is fixed and stable."},
        {"id": "S1-p2", "section": 1, "type": "p", "text": "Traders pay 25 percent of the value."},
        {"id": "S1-p3", "section": 1, "type": "p", "text": "This is a long paragraph with many words in it. It has two sentences."},
        {"id": "S1-p4", "section": 1, "type": "p", "text": "Traders may file online."},
        {"id": "S1-p5", "section": 1, "type": "p", "text": "This applies only once."},
    ]}
    decoy, planted = make_decoy(translation, ("negation", "number", "omission", "modality", "quantifier"))
    kinds = [p["kind"] for p in planted]
    assert kinds == ["negation", "number", "omission", "modality", "quantifier"]
    assert len({p["segment"] for p in planted}) == 5
    assert translation["segments"][0]["text"] == "The rate is fixed and stable."  # original untouched
    assert any("35" in s["text"] for s in decoy["segments"])


def test_score_catches_only_counts_flags_on_the_decoy_label():
    planted = [{"segment": "S1-p1", "kind": "number"}, {"segment": "S1-p2", "kind": "negation"}]
    judgment_flags = {"flags": [{"translator": "M6", "segment": "S1-p1"},
                                {"translator": "M1", "segment": "S1-p2"}]}
    caught = score_catches(judgment_flags, planted, "M6")
    assert caught == ["S1-p1"]
    assert caught_by_kind(planted, caught) == {"number": True, "negation": False}


# ---------------------------------------------------------------- aggregate


def test_kendall_tau_extremes_and_partial_overlap():
    assert kendall_tau(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert kendall_tau(["a", "b", "c"], ["c", "b", "a"]) == -1.0
    assert kendall_tau(["a", "b", "c", "d"], ["a", "c"]) == 1.0
    assert kendall_tau(["a"], ["a"]) is None


def test_borda_and_means_and_exclusion():
    judgments = [judgment("J1", ["M1", "M2", "M3"]), judgment("J2", ["M2", "M1", "M3"])]
    borda = borda_means(judgments, CODES)
    assert borda == {"M1": 2.5, "M2": 2.5, "M3": 1.0}
    assert criterion_means(judgments, CODES)["M1"]["meaning"] == 8
    calibration = [{"judge": "J1", "passed": False}, {"judge": "J2", "passed": True}]
    assert excluded_judges(calibration, judgments) == {"J1"}
    all_failed = [{"judge": "J1", "passed": False}, {"judge": "J2", "passed": False}]
    assert excluded_judges(all_failed, judgments) == set()


def test_agreement_and_position_consistency():
    judgments = [judgment("J1", ["M1", "M2", "M3"]), judgment("J2", ["M1", "M3", "M2"]),
                 judgment("J1", ["M3", "M2", "M1"], pass_name="reverse")]
    agreement = judge_agreement(judgments)
    assert round(agreement[("J1", "J2")], 2) == 0.33
    assert position_consistency(judgments) == {"J1": -1.0}


# ---------------------------------------------------------------- preflight


def test_preflight_validate_catches_broken_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "translator.md").write_text("$source_lang $target_lang $article_json $glossary")
    (tmp_path / "skills" / "judge.md").write_text(
        "$source_lang $target_lang $n_tr $labels $article_id $judge_code $ranking_stub "
        "$scores_stub $source_json $translations_block $glossary")
    cfg = {"translators": {"M1": "x", "bad": "y"}, "judges": {"J1": "z"},
           "prices": {"M1": {}}, "judge_prices": {},
           "calibration": {"label": "M1", "base_translator": "M9"},
           "request": {"max_retries": 0}}
    problems = validate(cfg)
    assert any("bad" in p for p in problems)
    assert any("judge_price" in p for p in problems)
    assert any("label clashes" in p for p in problems)
    assert any("base_translator" in p for p in problems)
    assert any("max_retries" in p for p in problems)
    cfg_ok = {"translators": {"M1": "x"}, "judges": {"J1": "z"}, "prices": {"M1": {}},
              "judge_prices": {"J1": {}}, "calibration": {"label": "M6", "base_translator": "M1"},
              "request": {"max_retries": 3}}
    assert validate(cfg_ok) == []
