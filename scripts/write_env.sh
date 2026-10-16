#!/usr/bin/env bash
# Copy the OpenRouter key from LibreChat into this project's .env
# (creates or updates the OPENROUTER_API_KEY line, mode 600) and verifies
# it against the OpenRouter API. Never prints the full key.
set -euo pipefail

cd "$(dirname "$0")/.."
VAR="OPENROUTER_API_KEY"
key="$(scripts/read_openrouter_key.sh --raw)"

if [ -f .env ] && grep -qE "^${VAR}=" .env; then
  sed -i -E "s|^${VAR}=.*|${VAR}=${key}|" .env
else
  printf '%s=%s\n' "$VAR" "$key" >> .env
fi
chmod 600 .env

status="$(curl -s -o /tmp/or_key_check.json -w '%{http_code}' \
  -H "Authorization: Bearer ${key}" https://openrouter.ai/api/v1/auth/key || true)"
if [ "$status" = "200" ]; then
  echo ".env written, key valid (${key:0:12}...${key: -4})"
  python3 -c "import json;d=json.load(open('/tmp/or_key_check.json')).get('data',{});print('label:',d.get('label'),'| usage USD:',d.get('usage'),'| limit:',d.get('limit'))" 2>/dev/null || true
else
  echo ".env written, but key check returned HTTP ${status}" >&2
  exit 1
fi
rm -f /tmp/or_key_check.json
