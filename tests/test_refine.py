"""Tests for the second pass (src.refine)."""
import json

from src import refine, translate

CFG = {"source_lang": "English", "target_lang": "Russian",
       "request": {"temperature": 0, "max_retries": 2, "timeout_sec": 10}}
SOURCE = {"article": "a1", "segments": [{"id": "S1-p1", "type": "p", "text": "May 2020"}]}
BASE = {"article": "a1", "translator": "M7", "segments": [{"id": "S1-p1", "type": "p", "text": "May 2020"}]}


def test_prompt_shows_source_only_when_asked():
    with_src = refine.build_prompt(CFG, SOURCE, BASE, True)
    without = refine.build_prompt(CFG, SOURCE, BASE, False)
    assert "SOURCE:" in with_src and "SOURCE:" not in without
    assert refine.SOURCE_RULE.strip() in with_src and refine.SOURCE_RULE.strip() not in without


def test_refine_one_returns_validated_result_with_metadata(monkeypatch):
    reply = json.dumps({"segments": [{"id": "S1-p1", "type": "p", "text": "May 2020 fixed"}]})
    monkeypatch.setattr(refine, "chat", lambda *a, **k: (reply, {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001}))
    spec = {"base": "M7", "model": "openai/gpt-6-luna-pro", "source": True}
    out = refine.refine_one(CFG, SOURCE, BASE, "H2", spec)
    assert out["translator"] == "H2" and out["base"] == "M7" and out["sees_source"] is True
    assert out["usage"]["prompt_tokens"] == 10


def test_refine_article_skips_when_base_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(refine, "OUT_DIR", tmp_path)
    src = tmp_path / "a1.json"
    src.write_text(json.dumps(SOURCE))
    failures = refine.refine_article(CFG, src, {"H1": {"base": "M7", "model": "m", "source": False}})
    assert failures == 1 and not (tmp_path / "tr__a1__H1.json").exists()


def test_translate_skips_hybrid_codes(tmp_path, monkeypatch):
    called = []
    cfg = {"translators": {"M7": "openai/gpt-6-sol-pro", "H1": "openai/gpt-6-luna-pro"},
           "hybrids": {"H1": {"base": "M7", "model": "openai/gpt-6-luna-pro"}}, "request": {}}
    (tmp_path / "a1.json").write_text(json.dumps(SOURCE))
    monkeypatch.setattr(translate, "SRC_DIR", tmp_path)
    monkeypatch.setattr(translate, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(translate, "load_cfg", lambda: cfg)
    monkeypatch.setattr(translate, "load_glossary", lambda c: ())
    monkeypatch.setattr(translate, "key_usage", lambda: None)
    monkeypatch.setattr(translate, "log_spend", lambda *a: None)
    monkeypatch.setattr(translate, "translate_one", lambda c, p, code, m, g: called.append(code) or dict(BASE))
    translate.main([])
    assert called == ["M7"]
