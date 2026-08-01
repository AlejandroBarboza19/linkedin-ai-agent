#!/usr/bin/env bash
set -euo pipefail

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

# Extraer ZAI_API_KEY de .env y escribirla en .opencode/zai-key
API_KEY=$(grep -E '^ZAI_API_KEY=' "$ENV_FILE" | head -1 | cut -d '=' -f2- | tr -d '[:space:]')
if [ -z "$API_KEY" ]; then
  echo "ERROR: ZAI_API_KEY no encontrada en $ENV_FILE" >&2
  exit 1
fi
printf '%s' "$API_KEY" > "$KEY_FILE"

# Ejecutar opencode desde el directorio del proyecto, o el repo se percibe
# como "directorio externo" y opencode bloquea el acceso en modo no interactivo.
cd "$PROJECT_DIR"

# Sin instrucción, publicar "Hola mundo" por defecto (demo en un solo comando).
DEFAULT_PROMPT="Publica un post 'Hola mundo'"
if [ "$#" -eq 0 ]; then
  set -- "$DEFAULT_PROMPT"
fi

exec opencode run --agent linkedin-agent "$@"
