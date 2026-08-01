#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Preparar la key desde .env (no publica nada).
"$SCRIPT_DIR/setup.sh"

# Ejecutar opencode desde el directorio del proyecto, o el repo se percibe
# como "directorio externo" y opencode bloquea el acceso en modo no interactivo.
cd "$PROJECT_DIR"

# Sin instrucción, publicar "Hola mundo" por defecto (demo en un solo comando).
DEFAULT_PROMPT="Publica un post 'Hola mundo'"
if [ "$#" -eq 0 ]; then
  set -- "$DEFAULT_PROMPT"
fi

exec opencode run --agent linkedin-agent "$@"
