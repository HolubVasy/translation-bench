#!/usr/bin/env bash
# Read the OpenRouter key that LibreChat already uses on this VPS.
# Prints a masked value by default; pass --raw to print the full key.
set -euo pipefail

CONTAINER="${LIBRECHAT_CONTAINER:-LibreChat}"
VAR="OPENROUTER_API_KEY"

line="$(docker exec "$CONTAINER" sh -c "grep -E '^${VAR}=' /app/.env" 2>/dev/null || true)"
if [ -z "$line" ]; then
  echo "no ${VAR} found in container ${CONTAINER} (/app/.env)" >&2
  exit 1
fi
key="${line#*=}"
if [ "${1:-}" = "--raw" ]; then
  printf '%s\n' "$key"
else
  printf '%s=%s...%s (len %d)\n' "$VAR" "${key:0:12}" "${key: -4}" "${#key}"
fi
