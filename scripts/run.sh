#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
KEY_FILE="$PROJECT_DIR/.opencode/openrouter-key"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env file not found at $ENV_FILE" >&2
  echo "" >&2
  echo "  To get started, copy the example file:" >&2
  echo "    cp $PROJECT_DIR/.env.example $ENV_FILE" >&2
  echo "  Then edit $ENV_FILE and set your OPENROUTER_API_KEY." >&2
  exit 1
fi

# Extract OPENROUTER_API_KEY from .env and write it to .opencode/openrouter-key
API_KEY=$(grep -E '^OPENROUTER_API_KEY=' "$ENV_FILE" | head -1 | cut -d '=' -f2- | tr -d '[:space:]')
if [ -z "$API_KEY" ]; then
  echo "ERROR: OPENROUTER_API_KEY not found in $ENV_FILE" >&2
  exit 1
fi
printf '%s' "$API_KEY" > "$KEY_FILE"

exec opencode run --agent linkedin-agent "$@"
