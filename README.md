# LinkedIn AI Agent

Proyecto de AI Agent Engineer: un sistema agéntico que publica contenido en LinkedIn usando OpenCode, el Protocolo de Contexto de Modelos (MCP) y Playwright — con Human in the Loop (HITL) obligatorio para la autenticación y las acciones críticas.

---

## Objetivo

Automatizar la publicación de contenido en LinkedIn mediante un agente basado en navegador que respeta los límites de seguridad de la plataforma. El agente nunca almacena credenciales y nunca automatiza el login ni el 2FA. La publicación se realiza automáticamente, pero solo después de la aprobación humana explícita del contenido. La autenticación (login + 2FA) siempre requiere intervención manual del usuario en un navegador visible.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    OpenCode Agent                        │
│  ┌─────────────────────────────────────────────────────┐│
│  │  agent: linkedin-agent                              ││
│  │  prompt: agents/linkedin_agent.md                   ││
│  │  model: zai/glm-5.2                                 ││
│  └──────────────┬──────────────────────────────────────┘│
│                 │                                       │
│  ┌──────────────▼──────────────────────────────────────┐│
│  │  Skill: linkedin-poster                             ││
│  │  - Validación pre-flight del contenido              ││
│  │  - Coordinación HITL (login / 2FA)                   ││
│  │  - Orquesta las herramientas MCP                    ││
│  └──────────────┬──────────────────────────────────────┘│
│                 │                                       │
│  ┌──────────────▼──────────────────────────────────────┐│
│  │  MCP Server: linkedin_server                        ││
│  │  - Transporte: stdio (subproceso local)             ││
│  │  - 5 herramientas registradas vía @server.tool()    ││
│  └──────────────┬──────────────────────────────────────┘│
│                 │                                       │
│  ┌──────────────▼──────────────────────────────────────┐│
│  │  Playwright (Chromium, navegador visible)           ││
│  │  - headless=False                                   ││
│  │  - Sin técnicas de stealth / evasión                ││
│  └──────────────┬──────────────────────────────────────┘│
│                 │                                       │
│  ┌──────────────▼──────────────────────────────────────┐│
│  │  LinkedIn (basado en navegador)                     ││
│  │  - login mediante interacción manual del usuario    ││
│  │  - 2FA mediante interacción manual del usuario      ││
│  │  - Publicación mediante clic automático              ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Roles de los componentes

| Capa | Rol |
|---|---|
| **OpenCode Agent** | Define la identidad del agente, las reglas de seguridad y las políticas HITL. Enruta las peticiones del usuario a la skill correspondiente. |
| **Skill** | Valida el contenido (longitud, datos sensibles, enlaces), coordina el flujo de publicación y aplica los puntos de control HITL. |
| **MCP Server** | Expone primitivas de control del navegador como herramientas. Se ejecuta como subproceso local por stdio. Las sesiones son en memoria y efímeras. |
| **Playwright** | Lanza un navegador Chromium visible. Toda la navegación e interacción con el DOM se realiza a través de la API asíncrona oficial de Playwright. |
| **LinkedIn** | Plataforma objetivo. Se accede exclusivamente a través del navegador — sin API keys, sin tokens, sin endpoints reversados. |

---

## Flujo Human in the Loop

```
El usuario solicita contenido por chat
    │
    ▼
Validación pre-flight del contenido (longitud, datos sensibles, enlaces)
    │
    ▼
[Gate 1] El agente muestra el preview y pregunta: "¿Confirmas que
         quieres publicar esto?" ─── No ──→ Vuelve a edición
    │ Sí
    ▼
open_browser_tool → Chromium visible en linkedin.com/login
    │
    ▼
[Gate 2] El agente notifica: "Navegador abierto. Inicia sesión."
         El usuario ingresa credenciales + 2FA en el navegador.
         wait_for_human_auth_tool sondea la URL hasta salir de /login
    │
    ▼
verify_session_tool → navega a /feed/ para confirmar cookies válidas
    │
    ▼
create_post_tool → abre el editor, escribe el contenido y hace clic
                   en "Publicar" automáticamente
    │
    ▼
close_browser_tool → descarta las cookies de sesión y cierra el navegador
    │
    ▼
El agente notifica el resultado por chat
```

**Dos puntos de control HITL obligatorios — coordinados por conversación:**

1. **Preview del contenido** — el agente pregunta por chat; el usuario aprueba o edita.
2. **Login + 2FA** — el agente abre el navegador y notifica al usuario; el usuario se autentica en el navegador visible; el agente detecta el cambio de URL.

Una vez autenticado y aprobado el contenido, el agente rellena el editor y hace clic en "Publicar" automáticamente.

---

## MCP Server: `linkedin_server`

Cinco herramientas registradas vía el SDK de MCP v2 (decorador `@server.tool()`):

### `open_browser_tool`
- **Entrada:** `session_id` (string opcional, se autogenera si está vacío)
- **Salida:** `{"status": "ok|error", "session_id": "...", "message": "..."}`
- **Acción:** Lanza un navegador Chromium visible y navega a `https://www.linkedin.com/login`. Registra un handler de `popup` para rastrear ventanas emergentes durante el flujo. Devuelve un ID de sesión para las llamadas posteriores.

### `wait_for_human_auth_tool`
- **Entrada:** `session_id` (string), `timeout_minutes` (int, por defecto 5)
- **Salida:** `{"status": "ok|error", "session_id": "...", "message": "..."}`
- **Acción:** Sondea `page.url` cada 2 segundos. Cuando la URL deja de contener `/login`, se asume que la autenticación fue exitosa. También detecta ventanas emergentes del flujo de seguridad (URLs con `checkpoint`, `feed` o `authwall`) como señal de autenticación. No interactúa con los campos de login.

### `verify_session_tool`
- **Entrada:** `session_id` (string)
- **Salida:** `{"status": "ok|error", "session_id": "...", "message": "...", "active": bool}`
- **Acción:** Navega a `https://www.linkedin.com/feed/`. Si es redirigido de vuelta a `/login`, marca la sesión como expirada.

### `create_post_tool`
- **Entrada:** `session_id` (string), `content` (string)
- **Salida:** `{"status": "ok|error", "session_id": "...", "message": "...", "content": "..."}`
- **Acción:** Navega a /feed/, si la ventana es demasiado pequeña la agranda automáticamente (los layouts responsivos de LinkedIn ocultan botones), descarta modales/upsells in-page (Premium/Plus, cookies) con Escape o botones de cierre, hace clic en "Start a post" (`div[role="button"]`), localiza el editor contenteditable (`div[contenteditable="true"][role="textbox"]`), escribe el contenido y hace clic en el botón de publicar ("Publicar"/"Post"/"Publish") automáticamente. Si no encuentra los botones, devuelve un error indicando que se maximice la ventana y se reintente. Luego espera a que se cierre el modal del editor para confirmar que el post fue publicado.

### `close_browser_tool`
- **Entrada:** `session_id` (string)
- **Salida:** `{"status": "ok|error", "session_id": "...", "message": "..."}`
- **Acción:** Cierra la página y el navegador, detiene el driver de Playwright y elimina la sesión de la memoria. Las cookies se descartan.

---

## Estructura del proyecto

```
linkedin-ai-agent/
├── agents/
│   └── linkedin_agent.md           # Definición del agente (identidad, reglas de seguridad)
├── mcp/
│   └── linkedin_server/
│       ├── __init__.py
│       ├── server.py               # Servidor MCP (MCPServer, 5 bindings de tools)
│       └── tools.py                # Lógica principal (automatización Playwright)
├── src/
│   ├── core/
│   │   └── config.py               # Settings Pydantic (ZAI_API_KEY, archivo env)
│   └── telemetry/
│       └── logger.py               # Configuración de logging
├── tests/
│   ├── test_mcp.py                 # 29 tests: tools MCP con Playwright mockeado
│   ├── test_agent.py               # Definición del agente + frontmatter de la skill
│   ├── test_config.py              # Settings: defaults + variables de entorno
│   └── test_harness.py             # Harness HITL por señal de archivo
├── scripts/
│   ├── run.ps1                     # Lanzador Windows PowerShell (setup + publica)
│   ├── run.cmd                     # Lanzador Windows CMD (setup + publica)
│   ├── run.sh                      # Lanzador Linux/macOS (setup + publica)
│   ├── setup.ps1                   # Solo configura la key (.env → .opencode/zai-key)
│   ├── setup.cmd                   # Igual que setup.ps1 pero para CMD
│   └── setup.sh                    # Igual que setup.ps1 pero para Linux/macOS
├── .opencode/
│   └── skills/
│       └── linkedin-poster/
│           └── SKILL.md            # Skill auto-descubierta por OpenCode
├── Dockerfile                      # Imagen del servidor MCP (Python + Chromium)
├── docker-compose.yml              # Definición del servicio en Compose
├── opencode.jsonc                  # Configuración de OpenCode (MCP, agente, modelo)
├── pyproject.toml                  # Dependencias Python y metadatos del proyecto
├── conftest.py                     # Setup de paths de pytest (imports de raíz)
├── run_test_flow.py                # Prueba del flujo end-to-end (llamadas directas a tools)
├── .github/workflows/ci.yml        # Pipeline CI (ruff + pytest + docker build)
└── .env.example                    # Plantilla de variables de entorno
```

---

## Prerrequisitos

- **Python** >= 3.11
- **Git**
- **Chromium** (instalado vía Playwright)
- **OpenCode** CLI (para ejecución basada en agente) — opcional, la invocación directa de tools funciona sin él
- **ZAI API key** (gratis, de https://z.ai) si usas el modelo GLM configurado vía OpenCode
- **Docker** (opcional) — solo para validar el entorno con `docker compose build`

---

## Primeros pasos en una máquina limpia

Si nunca has probado el proyecto, instala primero las herramientas base (una sola vez por máquina) y luego sigue los pasos del proyecto.

### 1. Herramientas base

| Herramienta | Para qué | Dónde |
|---|---|---|
| **Git** | Clonar el repositorio | https://git-scm.com |
| **Python 3.11+** | Ejecutar el proyecto | https://www.python.org (marca "Add to PATH" en Windows) |
| **Node.js** | Instalar el CLI de OpenCode | https://nodejs.org |
| **OpenCode CLI** | Ejecutar el agente | `npm install -g opencode-ai` |
| **Docker Desktop** *(opcional)* | Validar el entorno empaquetado | https://www.docker.com/products/docker-desktop |

Verifica que todo quedó instalado:

```bash
git --version
python --version          # o python3
node --version
npm --version
opencode --version
```

### 2. Instalar el proyecto

```bash
# 1. Clonar el repositorio
git clone https://github.com/AlejandroBarboza19/linkedin-ai-agent
cd linkedin-ai-agent

# 2. Crear y activar un entorno virtual
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Instalar el paquete y las dependencias de desarrollo
pip install -e ".[dev]"

# 4. Instalar Chromium para Playwright
playwright install chromium
```

### 3. Configurar la API key

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

Edita `.env` y pon tu `ZAI_API_KEY` (gratis en https://z.ai).

### 4. Probar

```bash
python -m pytest -q        # esperado: 38 passed
python -m ruff check .     # esperado: All checks passed!
scripts\setup.cmd          # Windows: prepara la key
scripts\run.cmd            # Windows: publica "Hola mundo"
./scripts/setup.sh         # macOS/Linux: prepara la key
./scripts/run.sh           # macOS/Linux: publica "Hola mundo"
```

---

## Instalación

Resumen de los pasos del proyecto (tras tener las herramientas base):

```bash
# 1. Clonar el repositorio
git clone https://github.com/AlejandroBarboza19/linkedin-ai-agent
cd linkedin-ai-agent

# 2. Crear y activar un entorno virtual
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Instalar el paquete y las dependencias de desarrollo
pip install -e ".[dev]"

# 4. Instalar Chromium para Playwright
playwright install chromium
```

---

## Configuración

Copia `.env.example` a `.env` y configura tu API key de ZAI:

```env
ZAI_API_KEY=tu-key-aqui
LOG_LEVEL=INFO
```

---

## Docker (empaquetado del entorno)

Docker empaqueta el servidor MCP con todas las dependencias para builds reproducibles y validación en CI. El flujo HITL requiere un navegador visible en el host — usa ejecución local para login y 2FA.

### Build

```bash
docker compose build
```

### Ejecutar (headless — sin UI del navegador)

```bash
docker compose run --rm linkedin-mcp-server
```

Esto inicia el servidor MCP en modo stdio. Valida que todas las dependencias resuelvan y que el servidor arranque correctamente.

### Qué incluye la imagen

| Componente | Detalle |
|---|---|
| Imagen base | `python:3.11-slim` |
| Dependencias de sistema | `libnss3`, `libnspr4`, `libatk1.0-0`, `libcups2`, `libdrm2`, `libgbm1`, etc. (requisitos de Chromium de Playwright) |
| Dependencias Python | Instaladas desde `pyproject.toml` vía `pip install -e ".[dev]"` |
| Chromium | Instalado vía `playwright install chromium` |

---

## Ejecución

### Ejecutar el agente

```bash
# 1. Copiar el archivo de ejemplo
cp .env.example .env

# 2. Editar .env y poner tu API key de ZAI (https://z.ai):
#    ZAI_API_KEY=tu-key-aqui

# 3. Ejecutar:
./scripts/run.sh "Crea un post en LinkedIn diciendo Hola mundo"   # Linux / macOS
.\scripts\run.ps1 "Crea un post en LinkedIn diciendo Hola mundo"  # Windows (PowerShell)
.\scripts\run.cmd "Crea un post en LinkedIn diciendo Hola mundo"  # Windows (CMD)
```

`run.sh`/`run.ps1` preparan la key y abren opencode en modo interactivo en un solo comando: leen `ZAI_API_KEY` de `.env`, la escriben en `.opencode/zai-key` (que opencode lee vía `{file:.opencode/zai-key}`; el archivo está gitignoreado), cambian al directorio del proyecto y abren la TUI con `opencode --agent linkedin-agent --prompt "tu instrucción"`. La TUI es **interactiva**: el agente pide confirmación por chat y tú respondes **"sí"** ahí mismo (en `opencode run` no interactivo no se puede responder y el flujo se bloquea).

Sin argumento, el script publica un post **"Hola mundo"** por defecto (demo en un solo comando). Si pasas una instrucción, usa la tuya:

```bash
./scripts/run.sh                                   # publica "Hola mundo"
./scripts/run.sh "Escribe un post sobre IA"        # usa tu instrucción
```

### Solo configurar la key (para usar opencode interactivo)

Si prefieres abrir opencode directamente y conversar, corre el setup **una vez**; luego `opencode` normal ya funciona cuando quieras:

```bash
./scripts/setup.sh        # Linux / macOS  (solo escribe .opencode/zai-key)
.\scripts\setup.ps1       # Windows (PowerShell)
.\scripts\setup.cmd       # Windows (CMD)
opencode                  # ya listo, sin exportar nada
```

### Nota sobre permisos de OpenCode

La TUI interactiva gestiona los permisos por pantalla. Si alguna vez usas `opencode run` no interactivo y OpenCode bloquea el acceso al proyecto como *"directorio externo"*, el `opencode.jsonc` ya incluye una regla de `permission` para permitir `$HOME/**`. Como alternativa, ejecuta con auto-aprobación:

```bash
opencode run --auto --agent linkedin-agent "Escribe un post sobre tendencias de IA"
```

### Flujo de prueba / demo (llamadas directas a tools)

Para verificar rápidamente el pipeline de automatización del navegador:

```bash
python run_test_flow.py
```

Este script llama directamente a las tools MCP (sin agente) y usa un archivo `.hitl_signal` para la confirmación HITL — apto para pruebas y CI.

### Flujo con agente (vía conversación en OpenCode — HITL real)

El flujo de producción usa la interfaz conversacional de OpenCode. La confirmación HITL ocurre por chat, no por señales de archivo.

Usa los scripts de `scripts/` para preparar la key automáticamente (ver [Ejecutar el agente](#ejecutar-el-agente) y [Solo configurar la key](#solo-configurar-la-key-para-usar-opencode-interactivo)):

```bash
./scripts/run.sh "Escribe un post sobre tendencias de IA"
```

O manualmente (primero corre el setup una vez):

```bash
./scripts/setup.sh   # escribe .opencode/zai-key desde tu .env
opencode
# Luego el prompt: @linkedin-agent "Escribe un post sobre tendencias de IA"
```

El agente orquesta el flujo completo:
1. Solicita contenido, valida, muestra preview y pide confirmación por chat
2. Abre el navegador, el usuario inicia sesión manualmente (navegador visible, incluido el 2FA)
3. Rellena el editor y hace clic en "Publicar" automáticamente
4. Cierra el navegador y reporta el resultado

### Vía servidor MCP (stdio)

```bash
python -m mcp.linkedin_server.server
```

El servidor escucha en stdin/stdout y puede ser conectado por cualquier cliente MCP. Las tools se invocan mediante el protocolo estándar de request/response de MCP.

---

## Testing

```bash
# Ejecutar todos los tests
pytest

# Ejecutar con salida verbose
pytest -v

# Ejecutar un archivo específico
pytest tests/test_mcp.py -v
```

**Cobertura de tests actual (38 tests):**

| Archivo de tests | Tests | Alcance |
|---|---|---|
| `tests/test_mcp.py` | 29 | Tools MCP con mockeo completo de Playwright |
| `tests/test_agent.py` | 3 | Definición del agente + frontmatter de la skill |
| `tests/test_config.py` | 2 | Defaults de settings y variables de entorno |
| `tests/test_harness.py` | 4 | Harness HITL por señal de archivo |

Todas las tools MCP están testeadas con `async_playwright` mockeado, cubriendo paths de éxito, manejo de errores y el flujo happy-path completo.

**Pipeline CI (`.github/workflows/ci.yml`):** `ruff check .` → `pytest` → `docker build` (valida la imagen del servidor MCP).

---

## Decisiones de seguridad

| Principio | Implementación |
|---|---|
| **Sin almacenamiento de credenciales** | Las credenciales nunca se leen, escriben ni loguean. Los campos de login nunca se rellenan programáticamente. |
| **Sin persistencia de cookies** | El contexto del navegador es efímero. Cerrar el navegador con `close_browser_tool` descarta todas las cookies de sesión. No se serializan cookies a disco. |
| **Sin bypass de autenticación** | El agente nunca intenta evadir login, 2FA, CAPTCHA ni ningún mecanismo de seguridad de LinkedIn. Solo detecta que la autenticación ocurrió. |
| **Privilegio mínimo** | El agente solo automatiza la creación de posts. No modifica perfiles, envía mensajes, gestiona conexiones ni realiza acciones fuera del flujo de publicación. |
| **Audit logging** | Un componente de logging está disponible en `src/telemetry/logger.py` para registros con timestamp (las credenciales nunca se incluyen). |
| **Aislamiento de sesiones** | Cada ejecución crea una sesión nueva de Playwright. Los IDs de sesión son UUIDs que solo viven en memoria. Ejecuciones consecutivas no comparten estado. |

---

## Limitaciones

| Limitación | Descripción | Mejora potencial |
|---|---|---|
| **Sin persistencia de sesión** | Las sesiones son solo en memoria. Si la conexión MCP se cae, el navegador se cierra. | Implementar serialización del contexto del navegador o un servidor de larga duración con keepalive. |
| **Selectores dependientes del locale** | El selector del botón "Start a post" apunta al texto en español (`name="Crear"`). Falla en inglés u otros idiomas. | Usar selectores por rol ARIA o detectar el locale desde los metadatos de la página. |
| **Sin test e2e en CI** | El workflow de CI solo ejecuta unit tests con mocks. Los tests reales de Playwright requieren un servidor de display. | Añadir un job de CI con `xvfb` para Playwright headful en CI. |
| **Popup y modales de LinkedIn** | Se rastrean popups y se descartan modales in-page, pero una ventana emergente desconocida podría interceptar el flujo. | Ampliar el mapeo de URLs de popup y selectores de cierre según cambios de UI de LinkedIn. |
| **Sin soporte de imágenes/video** | Actualmente solo posts de texto plano. | Extender `create_post_tool` para manejar subidas de medios en el editor de LinkedIn. |
| **Recuperación de errores** | Si el usuario cierra la pestaña del navegador a mitad del flujo, la tool devuelve un error y termina. | Añadir detección de crash del navegador y lógica de recuperación de sesión. |
| **Cambios en el DOM de LinkedIn** | Los selectores (`div[role="button"]`, `div[contenteditable="true"]`) pueden romperse si LinkedIn actualiza su UI. | Añadir una tool de health-check de selectores y estrategias de fallback. |

---

## Licencia

MIT
