"""Unit tests for the JSON extraction and usage helpers."""

import pytest

from src.openrouter import add_usage, extract_json


@pytest.mark.parametrize("reply", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    'Sure, here it is:\n{"a": 1}\nHope this helps.',
    '\ufeff{"a": 1}',
    '{"a": 1,}',
    '{"a": [1, 2,], }',
])
def test_extract_json_tolerates_wrappers(reply):
    assert extract_json(reply) == {"a": 1} or extract_json(reply) == {"a": [1, 2]}


def test_extract_json_keeps_newlines_and_tabs_inside_strings():
    assert extract_json('{"t": "a\\nb\\tc"}') == {"t": "a\nb\tc"}


def test_extract_json_drops_control_characters():
    assert extract_json('{"t": "x\u0007y\u0000z"}') == {"t": "xyz"}


def test_extract_json_handles_braces_inside_strings():
    value = extract_json('{"t": "has } and { braces", "n": {"m": 2}}')
    assert value["n"] == {"m": 2}


def test_extract_json_raises_without_object():
    with pytest.raises(ValueError):
        extract_json("no json at all")
    with pytest.raises(ValueError):
        extract_json(None)


def test_add_usage_sums_tokens_and_latency():
    spent = {}
    add_usage(spent, {"prompt_tokens": 10, "completion_tokens": 5, "latency_sec": 1.5})
    add_usage(spent, {"prompt_tokens": 7, "latency_sec": 0.25})
    add_usage(spent, None)
    assert spent == {"prompt_tokens": 17, "completion_tokens": 5,
                     "latency_sec": 0.0, "latency_total_sec": 1.75}


def test_extract_json_survives_backticks_inside_a_string():
    reply = '{"segments": [{"id": "S1-p1", "text": "use ```code``` here"}]}'
    assert extract_json(reply)["segments"][0]["text"] == "use ```code``` here"


def test_add_usage_sums_exact_cost_when_reported():
    spent = {}
    add_usage(spent, {"prompt_tokens": 1, "cost": 0.1})
    add_usage(spent, {"prompt_tokens": 1, "cost": 0.05})
    assert spent["cost"] == 0.15
