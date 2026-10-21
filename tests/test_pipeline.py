"""Unit tests for judge validation, ordering, calibration planters and aggregation."""

import json

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


def test_disqualified_translation_counts_as_zero_where_it_was_gated_out():
    judged = [judgment("J1", ["M1", "M2"]), judgment("J1", ["M1", "M2", "M3"])]
    judged[0]["article"] = "a1"
    judged[1]["article"] = "a2"
    disqualified = {("a1", "M3"): ["length ratio"]}
    borda = borda_means(judged, CODES, disqualified)
    assert borda["M3"] == 0.5  # 0 on a1, 1 on a2
    means = criterion_means(judged, CODES, disqualified)
    assert means["M3"]["meaning"] == 4.0  # 0 on a1, 8 on a2
    assert borda_means(judged, CODES)["M3"] == 1.0  # without the gate info, a1 is simply absent


def test_stale_scores_of_a_gated_translation_are_ignored():
    judged = [judgment("J1", ["M3", "M1", "M2"])]
    judged[0]["article"] = "a1"
    disqualified = {("a1", "M3"): ["length ratio"]}
    assert borda_means(judged, CODES, disqualified) == {"M1": 2.0, "M2": 1.0, "M3": 0.0}
    assert criterion_means(judged, CODES, disqualified)["M3"]["meaning"] == 0


def test_validate_judgment_returns_problems_for_malformed_replies():
    assert validate_judgment(None, CODES) == ["reply is not a JSON object"]
    assert "ranking is not a permutation" in validate_judgment({"ranking": None, "scores": {}}, CODES)[0]
    assert validate_judgment({"ranking": CODES, "scores": None}, CODES) == ["scores is not an object"]
    assert validate_judgment({"ranking": CODES, "scores": {"M1": 5}}, CODES)[0] == "no scores for M1"


def test_judge_refuses_a_translation_without_gate_record(tmp_path, monkeypatch):
    import pytest
    from src import judge
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "checks").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        judge.is_disqualified("a1", "M1")
    (tmp_path / "data" / "checks" / "mech__a1__M1.json").write_text('{"disqualified": true}')
    assert judge.is_disqualified("a1", "M1") is True


def test_validate_judgment_handles_string_and_null_scores_without_raising():
    bad = judgment("J1", CODES)
    bad["scores"]["M1"]["meaning"] = "8"
    bad["scores"]["M2"]["flow"] = None
    bad["scores"]["M3"]["clean"] = True
    errors = validate_judgment(bad, CODES)
    assert errors == ["M1.meaning out of range", "M2.flow out of range", "M3.clean out of range"]


def test_assemble_falls_back_when_the_winner_is_gated_out_on_an_article(tmp_path, monkeypatch):
    from src import assemble
    monkeypatch.chdir(tmp_path)
    for folder in ("data/checks", "data/judgments", "data/calibration"):
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "config.yaml").write_text("translators: {M1: a, M2: b, M3: c}\n")
    (tmp_path / "data/checks/mech__a2__M1.json").write_text('{"disqualified": true}')
    j = judgment("J1", ["M1", "M3", "M2"])
    j["article"] = "a2"
    (tmp_path / "data/judgments/ev__a2__by__J1.json").write_text(json.dumps(j))
    assert assemble.pick_for_article("a1", "M1") == "M1"
    assert assemble.pick_for_article("a2", "M1") == "M3"


def test_make_decoy_defaults_to_every_planter():
    from src.calibrate import PLANTERS
    translation = {"article": "1", "segments": [
        {"id": "S1-p%d" % i, "section": 1, "type": "p", "text": t} for i, t in enumerate([
            "The rate is fixed and stable.", "Traders pay 25 percent of the value.",
            "This is a long paragraph with many words in it. It has two sentences.",
            "Traders may file online.", "This applies only once."])]}
    _, planted = make_decoy(translation)
    assert [p["kind"] for p in planted] == list(PLANTERS)


def test_validate_judgment_checks_flags_shape():
    ok = judgment("J1", CODES)
    ok.pop("flags")
    assert validate_judgment(ok, CODES) == [] and ok["flags"] == []
    bad = judgment("J1", CODES)
    bad["flags"] = None
    assert validate_judgment(bad, CODES) == [] and bad["flags"] == []
    bad["flags"] = "none"
    assert validate_judgment(bad, CODES) == ["flags is not a list"]
    bad["flags"] = [None]
    assert validate_judgment(bad, CODES) == ["flags contains a non-object entry"]


def test_validate_translation_never_raises():
    from src.translate import validate_translation
    source = {"segments": [{"id": "S1-p1", "type": "p", "text": "x"}]}
    assert validate_translation(source, {"segments": None}) == ["segments is not a list"]
    assert validate_translation(source, None) == ["segments is not a list"]
    assert validate_translation(source, {"segments": ["x"]}) == ["S1-p1: segment is not an object"]
    numeric = {"segments": [{"id": "S1-p1", "type": "p", "text": 2024}]}
    assert validate_translation(source, numeric) == ["S1-p1: text is not a string"]


def test_gated_translation_gets_zero_on_an_article_nobody_judged():
    judged = [judgment("J1", ["M1", "M2"])]
    judged[0]["article"] = "a1"
    disqualified = {("a2", "M3"): ["residue"], ("a1", "M3"): ["residue"]}
    borda = borda_means(judged, CODES, disqualified)
    assert borda["M3"] == 0.0
    assert criterion_means(judged, CODES, disqualified)["M3"]["meaning"] == 0


def test_gated_zero_weight_is_one_per_round_whatever_survived():
    from src.aggregate import gated_slots, per_judge_totals
    j1, j2 = judgment("J1", ["M1", "M2"]), judgment("J2", ["M1", "M2"])
    j1["article"] = j2["article"] = "a1"
    judged = [j1, j2]
    disqualified = {("a1", "M3"): ["x"], ("a2", "M3"): ["x"]}
    slots = gated_slots(judged, CODES, disqualified)
    assert sorted(slots) == [("a1", "M3", "J1"), ("a1", "M3", "J2"), ("a2", "M3", "J1"), ("a2", "M3", "J2")]
    totals = per_judge_totals(judged, CODES, disqualified)
    assert totals["J1"]["M3"] == [0, 0] and totals["J1"]["M1"] == [48]


def test_existing_judgment_is_reused_only_for_the_same_admitted_set(tmp_path):
    from src.judge import judged_same_set
    path = tmp_path / "ev__a1__by__J1.json"
    path.write_text(json.dumps({"presentation_order": ["M2", "M1"]}))
    assert judged_same_set(path, {"M1": "", "M2": ""})
    assert not judged_same_set(path, {"M1": "", "M2": "", "M3": ""})


def test_actual_spend_spans_the_run_and_usage_cost_prefers_exact_cost():
    from src.aggregate import actual_spend, usage_cost
    log = [{"before": 10.0, "after": 10.0}, {"before": 10.3, "after": 10.6}, {"before": 10.9, "after": 11.0}]
    assert round(actual_spend(log), 4) == 1.0
    assert actual_spend([]) is None
    assert usage_cost({"prompt_tokens": 1000000, "cost": 0.25}, {"input": 10}) == 0.25
    assert usage_cost({"prompt_tokens": 1000000}, {"input": 10}) == 10.0


def test_usage_cost_adds_an_estimate_for_attempts_without_cost():
    from src.aggregate import usage_cost
    from src.openrouter import add_usage
    spent = {}
    add_usage(spent, {"prompt_tokens": 1000000, "completion_tokens": 0, "cost": 0.5})
    add_usage(spent, {"prompt_tokens": 1000000, "completion_tokens": 0})
    assert usage_cost(spent, {"input": 2.0, "output": 0}) == 2.5


def test_converter_filters_and_stop_heading():
    from collections import Counter
    from src.convert import _real_words, is_layout_debris, is_page_furniture, is_stop_heading
    ctx = {"is_heading": lambda b: False, "n_pages": 10, "repeat_min": 3,
           "repeats": Counter({"cellulose (#) #:#-#": 9})}
    debris = {"text": "j j t t", "margin": False}
    formula = {"text": "= + x B (1) 0.55 1.18", "margin": False}
    prose = {"text": "The membranes were swelled in a mobile phase.", "margin": False}
    assert is_layout_debris(debris, ctx) and is_layout_debris(formula, ctx)
    assert not is_layout_debris(prose, ctx)
    assert is_page_furniture({"text": "Cellulose (2025) 32:2937-2954", "margin": True}, ctx)
    assert is_page_furniture({"text": "12", "margin": True}, ctx)
    assert not is_page_furniture(prose, ctx)
    assert is_stop_heading("REFERENCES", {"references"})
    assert is_stop_heading("* References:", {"references"})
    assert not is_stop_heading("References were checked by hand", {"references"})
    assert _real_words("Lys Area x 100") == ["Lys", "Area"]


def test_assemble_strips_xml_invalid_control_characters():
    from src.assemble import xml_safe
    assert xml_safe("a\x00b\x07c\x0bd\ttab\nline") == "abcd\ttab\nline"


def test_validate_judgment_keeps_agreed_flag_type_and_severity():
    ok = judgment("J1", CODES)
    ok["flags"] = [{"translator": "M1", "segment": "S1-p1", "criterion": "clean",
                    "type": "untranslated", "severity": "minor", "quote": "x"}]
    assert validate_judgment(ok, CODES) == []
    assert ok["flags"][0]["type"] == "untranslated"
    assert ok["flags"][0]["severity"] == "minor"


def test_validate_judgment_marks_unknown_flag_type_and_severity_unspecified():
    ok = judgment("J1", CODES)
    ok["flags"] = [{"translator": "M1", "segment": "S1-p1", "type": "typo", "severity": "huge"},
                   {"translator": "M1", "segment": "S1-p2"}]
    assert validate_judgment(ok, CODES) == []
    assert [f["type"] for f in ok["flags"]] == ["unspecified", "unspecified"]
    assert [f["severity"] for f in ok["flags"]] == ["unspecified", "unspecified"]
