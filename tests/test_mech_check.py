"""Unit tests for segment checks and gates."""

from src.mech_check import (DEFAULT_GATES, check_glossary, check_list_marker, check_numbers,
                            check_segments, check_source_script, check_urls, run_gates)


def seg(seg_id, text, kind="p"):
    return {"id": seg_id, "section": 1, "type": kind, "text": text}


def article(*texts):
    return {"article": "1", "segments": [seg("S1-p%d" % (i + 1), t) for i, t in enumerate(texts)]}


GLOSSARY = [{"source": "customs declaration", "target": ["customs declaration"]},
            {"source": "declarant", "target": ["declarant", "the declarant"]}]


def test_numbers_catch_changed_and_normalize_locale():
    assert check_numbers(seg("s", "price 1,5 and 25%"), seg("s", "price 1.5 and 25%"), []) is None
    issue = check_numbers(seg("s", "price 25%"), seg("s", "price 52%"), [])
    assert issue["missing"] == ["25"] and issue["extra"] == ["52"]


def test_urls_must_survive():
    issue = check_urls(seg("s", "see https://example.com/x"), seg("s", "see the link"), [])
    assert issue["missing"] == ["https://example.com/x"]


def test_list_marker_must_match():
    assert check_list_marker(seg("s", "- item"), seg("s", "- item"), []) is None
    assert check_list_marker(seg("s", "- item"), seg("s", "item"), [])["missing"] == ["list marker"]
    assert check_list_marker(seg("s", "1) item"), seg("s", "text"), []) is not None


def test_glossary_requires_an_approved_target_form():
    src = seg("s", "The Declarant files a customs declaration.")
    assert check_glossary(src, seg("s", "the declarant files a customs declaration"), GLOSSARY) is None
    issue = check_glossary(src, seg("s", "the applicant files a customs form"), GLOSSARY)
    assert sorted(issue["missing"]) == ["customs declaration", "declarant"]


def test_source_script_residue_is_counted():
    issue = check_source_script(seg("s", "x"), seg("s", "partly \u043f\u0435\u0440\u0435\u0432\u0435\u0434\u0435\u043d\u043e"), [])
    assert issue["extra"] == ["10 cyrillic chars"]
    assert check_source_script(seg("s", "[IMAGE_1]", "image"), seg("s", "[IMAGE_1]", "image"), []) is None


def test_check_segments_reports_missing_segment():
    source = article("one", "two")
    translation = {"article": "1", "segments": [seg("S1-p1", "one")]}
    issues = check_segments(source, translation, [])
    assert issues == [{"segment": "S1-p2", "kind": "missing_segment"}]


def test_gates_disqualify_on_length_and_residue():
    source = article("one two three four five six seven eight nine ten")
    short = article("one")
    assert any("length ratio" in r for r in run_gates(source, short, [], DEFAULT_GATES))
    ok = article("one two three four five six seven eight nine ten")
    assert run_gates(source, ok, [], DEFAULT_GATES) == []
    residue = [{"segment": "S1-p1", "kind": "source_script", "missing": [], "extra": ["4 cyrillic chars"]}]
    assert run_gates(source, ok, residue, DEFAULT_GATES) == ["4 source-script chars left in the translation"]


def test_gates_disqualify_on_glossary_and_missing_segments():
    source = article("a b c d")
    tr = article("a b c d")
    too_many = [{"segment": "S1-p1", "kind": "glossary", "missing": ["x", "y", "z", "w"], "extra": []}]
    assert run_gates(source, tr, too_many, DEFAULT_GATES) == ["4 glossary violations"]
    missing = [{"segment": "S1-p2", "kind": "missing_segment"}]
    assert run_gates(source, tr, missing, DEFAULT_GATES) == ["missing segments: S1-p2"]
