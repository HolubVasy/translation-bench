"""Minimal OpenRouter client."""

import json
import os
import re
import time

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(Exception):
    pass


def _api_key():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise OpenRouterError("OPENROUTER_API_KEY is not set (see .env.example)")
    return key


def chat(model, prompt, temperature=0.0, timeout=300, max_retries=3):
    """Send one user message, return (text, usage dict)."""
    headers = {
        "Authorization": "Bearer " + _api_key(),
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=body, timeout=timeout)
            if resp.status_code != 200:
                raise OpenRouterError(
                    "HTTP %d from %s: %s" % (resp.status_code, model, resp.text[:300])
                )
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return text, usage
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
