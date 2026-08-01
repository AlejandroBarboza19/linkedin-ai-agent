#!/usr/bin/env bash
set -euo pipefail

# Configuración: lee .env y escribe .opencode/zai-key para que opencode pueda
# usar el modelo zai. No publica nada.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
KEY_FILE="$PROJECT_DIR/.opencode/zai-key"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Archivo .env no encontrado en $ENV_FILE" >&2
  echo "" >&2
  echo "  Para empezar, copia el archivo de ejemplo:" >&2
  echo "    cp $PROJECT_DIR/.env.example $ENV_FILE" >&2
  echo "  Luego edita $ENV_FILE y configura tu ZAI_API_KEY (gratis en https://z.ai)." >&2
  exit 1
fi

# Extraer ZAI_API_KEY de .env y escribirla en .opencode/zai-key (que opencode
# lee vía {file:.opencode/zai-key}). El archivo está gitignoreado.
API_KEY=$(grep -E '^ZAI_API_KEY=' "$ENV_FILE" | head -1 | cut -d '=' -f2- | tr -d '[:space:]')
if [ -z "$API_KEY" ]; then
  echo "ERROR: ZAI_API_KEY no encontrada en $ENV_FILE" >&2
  exit 1
fi
mkdir -p "$PROJECT_DIR/.opencode"
printf '%s' "$API_KEY" > "$KEY_FILE"
chmod 600 "$KEY_FILE" 2>/dev/null || true

echo "Listo: key escrita en $KEY_FILE"
