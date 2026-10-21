"""Tests for the showcase tools: public protocol export and self-contained report."""
import json

import yaml

from tools import build_report, export_session


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj) if not isinstance(obj, str) else obj)


def make_run(tmp_path):
    cfg = {"translators": {"M1": "openai/gpt-6-luna-pro"}, "judges": {"J1": "anthropic/claude-opus-5.5"},
           "prices": {"M1": {"input": 0.1, "output": 0.5}}}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    data = tmp_path / "data"
    for art in ("a1", "a2", "a3"):
        write(data / "source" / (art + ".json"), {"segments": [{"text": "secret source words here"}]})
        write(data / "translations" / ("tr__%s__M1.json" % art),
              {"usage": {"prompt_tokens": 100, "completion_tokens": 200}})
        scores = {c: 8 for c in export_session.CRITERIA}
        write(data / "judgments" / ("ev__%s__by__J1.json" % art),
              {"article": art, "judge": "J1", "scores": {"M1": scores},
               "flags": [{"translator": "M1", "segment": "S1-p1", "criterion": "clean",
                          "type": "untranslated", "severity": "minor", "quote": "SECRET QUOTE"}]})
    write(data / "calibration" / "cal__by__J1.json", {"planted": [1, 2, 3, 4, 5], "caught": [1, 2, 3], "needed": 3, "passed": True})
    return data


def test_export_session_keeps_raw_facts_and_drops_text(tmp_path):
    data = make_run(tmp_path)
    export_session.main("2026-01-01", str(data), str(tmp_path / "out"))
    folder = tmp_path / "out" / "sessions" / "2026-01-01"
    verdicts = (folder / "verdicts.json").read_text()
    session = json.loads((folder / "session.json").read_text())
    assert "SECRET QUOTE" not in verdicts and "S1-p1" not in verdicts
    assert json.loads(verdicts)[0]["flags"] == [{"criterion": "clean", "type": "untranslated", "severity": "minor"}]
    assert [p["id"] for p in session["papers"]] == ["A", "B", "C"]
    assert "secret source" not in (folder / "session.json").read_text()
    assert session["translators"]["M1"]["tokens"]["A"] == {"input": 100, "output": 200}


def test_build_report_embeds_latest_session(tmp_path):
    data = make_run(tmp_path)
    export_session.main("2026-01-01", str(data), str(tmp_path / "out"))
    template = tmp_path / "index.html"
    template.write_text("<html><body>" + build_report.MARK + "\nstart();\n</script></body></html>")
    out = tmp_path / "report.html"
    assert build_report.main(str(template), str(tmp_path / "out"), str(out)) == 0
    html = out.read_text()
    assert html.index("window.TB_EMBED") < html.index(build_report.MARK)
    assert '"latest": "2026-01-01"' in html


def test_build_report_refuses_template_without_marker(tmp_path):
    data = make_run(tmp_path)
    export_session.main("2026-01-01", str(data), str(tmp_path / "out"))
    template = tmp_path / "index.html"
    template.write_text("<html></html>")
    assert build_report.main(str(template), str(tmp_path / "out"), str(tmp_path / "r.html")) == 1


def test_export_session_skips_reverse_pass(tmp_path):
    data = make_run(tmp_path)
    scores = {c: 1 for c in export_session.CRITERIA}
    write(data / "judgments" / "ev__a1__by__J1__r.json",
          {"article": "a1", "judge": "J1", "pass": "reverse", "scores": {"M1": scores}, "flags": []})
    export_session.main("2026-01-01", str(data), str(tmp_path / "out"))
    rows = json.loads((tmp_path / "out" / "sessions" / "2026-01-01" / "verdicts.json").read_text())
    assert len(rows) == 3 and all(r["scores"]["meaning"] == 8 for r in rows)


def test_export_session_survives_missing_calibration_and_translation(tmp_path):
    data = make_run(tmp_path)
    (data / "calibration" / "cal__by__J1.json").unlink()
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text())
    cfg["translators"]["M2"] = "openai/gpt-6-sol-pro"
    cfg["prices"]["M2"] = {"input": 2, "output": 10}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    export_session.main("2026-01-01", str(data), str(tmp_path / "out"))
    session = json.loads((tmp_path / "out" / "sessions" / "2026-01-01" / "session.json").read_text())
    assert session["judges"]["J1"]["calibration"] is None
    assert list(session["translators"]) == ["M1"]


def test_export_session_labels_any_number_of_papers(tmp_path):
    data = make_run(tmp_path)
    (data / "source" / "a3.json").unlink()
    export_session.main("2026-01-01", str(data), str(tmp_path / "out"))
    folder = tmp_path / "out" / "sessions" / "2026-01-01"
    session = json.loads((folder / "session.json").read_text())
    rows = json.loads((folder / "verdicts.json").read_text())
    assert [p["id"] for p in session["papers"]] == ["A", "B"]
    assert sorted({r["paper"] for r in rows}) == ["A", "B"]
