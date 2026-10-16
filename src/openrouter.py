"""Minimal OpenRouter client."""

import json
import os
import re
import time

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(Exception):
    pass


class ValidationFailed(RuntimeError):
    """All attempts answered but none passed validation. Carries the
    usage of those billed attempts so it can still be counted."""

    def __init__(self, message, usage):
        super().__init__(message)
        self.usage = usage


def _api_key():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise OpenRouterError("OPENROUTER_API_KEY is not set (see .env.example)")
    return key


def _post(body, headers, timeout):
    resp = requests.post(API_URL, headers=headers, json=body, timeout=timeout)
    return resp.status_code, resp.text


def chat(model, prompt, temperature=0.0, timeout=300, max_retries=3, max_tokens=None):
    """Send one user message, return (text, usage dict).

    Some reasoning models reject the temperature parameter with HTTP 400;
    in that case the request is retried once without it.
    """
    headers = {
        "Authorization": "Bearer " + _api_key(),
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens:
        body["max_tokens"] = max_tokens
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            status, text = _post(body, headers, timeout)
            if status == 400 and "temperature" in text.lower() and "temperature" in body:
                body.pop("temperature")
                status, text = _post(body, headers, timeout)
            if status != 200:
                raise OpenRouterError("HTTP %d from %s: %s" % (status, model, text[:300]))
            data = json.loads(text)
            if "error" in data:
                raise OpenRouterError("%s: %s" % (model, str(data["error"])[:300]))
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return content, usage
        except Exception as err:  # noqa: BLE001
            last_err = err
            if attempt < max_retries:
                time.sleep(5 * attempt)
    raise OpenRouterError("model %s failed after %d attempts: %s" % (model, max_retries, last_err))


def extract_json(text):
    """Parse a JSON object from a model reply, tolerating markdown fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return json.loads(text[start : end + 1])


def add_usage(total, usage):
    """Accumulate token usage across attempts, so failed but billed
    attempts still reach the spend table."""
    for key in ("prompt_tokens", "completion_tokens"):
        total[key] = total.get(key, 0) + int((usage or {}).get(key, 0) or 0)
    return total


KEY_URL = "https://openrouter.ai/api/v1/auth/key"
SPEND_LOG = "data/report/spend_log.jsonl"


def key_usage():
    """Cumulative USD spent on the API key, as OpenRouter reports it.
    None when the key or the network is unavailable."""
    try:
        resp = requests.get(KEY_URL, headers={"Authorization": "Bearer " + _api_key()},
                            timeout=15)
        if resp.status_code != 200:
            return None
        return float(resp.json().get("data", {}).get("usage"))
    except Exception:  # noqa: BLE001
        return None


def log_spend(stage, before, after):
    """Append one paid stage run to the spend log (key usage delta)."""
    if before is None or after is None:
        return
    import datetime
    from pathlib import Path as _Path
    path = _Path(SPEND_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"stage": stage, "before": before, "after": after,
              "at": datetime.datetime.utcnow().isoformat(timespec="seconds")}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def run_stamp():
    import datetime
    return datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
