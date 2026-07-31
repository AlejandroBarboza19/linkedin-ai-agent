# LinkedIn AI Agent

AI Agent Engineer project: an agentic system that publishes LinkedIn content using OpenCode, the Model Context Protocol (MCP), and Playwright — with mandatory Human in the Loop for authentication and critical actions.

---

## Objective

Automate LinkedIn content publication through a browser-based agent that respects the platform's security boundaries. The agent never stores credentials, never automates login or 2FA, and never publishes without explicit human confirmation. Every sensitive step requires manual user intervention.

---

## Architecture

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
│  │  - Pre-flight content validation                    ││
│  │  - HITL coordination (login / publish)              ││
│  │  - Orchestrates MCP tools                           ││
│  └──────────────┬──────────────────────────────────────┘│
│                 │                                       │
│  ┌──────────────▼──────────────────────────────────────┐│
│  │  MCP Server: linkedin_server                        ││
│  │  - Transport: stdio (local subprocess)               ││
│  │  - 5 tools registered via @server.tool()             ││
│  └──────────────┬──────────────────────────────────────┘│
│                 │                                       │
│  ┌──────────────▼──────────────────────────────────────┐│
│  │  Playwright (Chromium, visible browser)              ││
│  │  - headless=False                                    ││
│  │  - No stealth / evasion techniques                   ││
│  └──────────────┬──────────────────────────────────────┘│
│                 │                                       │
│  ┌──────────────▼──────────────────────────────────────┐│
│  │  LinkedIn (browser-based)                           ││
│  │  - login via manual user interaction                 ││
│  │  - 2FA via manual user interaction                   ││
│  │  - Publish via manual click                          ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Component roles

| Layer | Role |
|---|---|
| **OpenCode Agent** | Defines agent identity, safety rules, and HITL policies. Routes user requests to the appropriate skill. |
| **Skill** | Validates content (length, sensitive data, links), coordinates the publication flow, and enforces HITL gates. |
| **MCP Server** | Exposes browser control primitives as tools. Runs as a local stdio subprocess. Sessions are in-memory and ephemeral. |
| **Playwright** | Launches a visible Chromium browser. All navigation and DOM interaction happens through the official Playwright async API. |
| **LinkedIn** | Target platform. Accessed exclusively through the browser — no API keys, no tokens, no reverse-engineered endpoints. |

---

## Human in the Loop Flow

```
User requests content via chat
    │
    ▼
Pre-flight content validation (length, sensitive data, links)
    │
    ▼
[Gate 1] Agent shows preview and asks: "¿Confirmas que
         quieres publicar esto?" ─── No ──→ Back to editing
    │ Yes
    ▼
open_browser_tool → visible Chromium at linkedin.com/login
    │
    ▼
[Gate 2] Agent notifies: "Navegador abierto. Inicia sesión."
         User enters credentials + 2FA in the browser.
         wait_for_human_auth_tool polls URL until /login is left
    │
    ▼
verify_session_tool → navigates to /feed/ to confirm cookie validity
    │
    ▼
create_post_tool → opens editor, fills content
                   ("Post" button is NOT clicked automatically)
    │
    ▼
[Gate 3] Agent asks via chat: "El post está listo en el editor.
         Revisa el contenido y haz clic en 'Publicar' si estás de acuerdo."
         User clicks "Post" manually, then confirms in chat.
    │
    ▼
close_browser_tool → discards session cookies, closes browser
    │
    ▼
Agent notifies result via chat
```

**Three mandatory HITL gates — all coordinated via conversation:**

1. **Content preview** — agent asks by chat, user approves or edits.
2. **Login + 2FA** — agent opens the browser and notifies the user; the user authenticates in the visible browser; the agent detects the URL change.
3. **Final publish** — agent fills the editor, asks for approval by chat; the user manually clicks "Post" in the browser and confirms by chat.

---

## MCP Server: `linkedin_server`

Five tools registered via the MCP SDK v2 (`@server.tool()` decorator):

### `open_browser_tool`
- **Input:** `session_id` (optional string, auto-generated if empty)
- **Output:** `{"status": "ok|error", "session_id": "...", "message": "..."}`
- **Action:** Launches a visible Chromium browser and navigates to `https://www.linkedin.com/login`. Returns a session ID for subsequent tool calls.

### `wait_for_human_auth_tool`
- **Input:** `session_id` (string), `timeout_minutes` (int, default 5)
- **Output:** `{"status": "ok|error", "session_id": "...", "message": "..."}`
- **Action:** Polls `page.url` every 2 seconds. When the URL no longer contains `/login`, authentication is assumed successful. Does not interact with login fields.

### `verify_session_tool`
- **Input:** `session_id` (string)
- **Output:** `{"status": "ok|error", "session_id": "...", "message": "...", "active": bool}`
- **Action:** Navigates to `https://www.linkedin.com/feed/`. If redirected back to `/login`, marks session as expired.

### `create_post_tool`
- **Input:** `session_id` (string), `content` (string)
- **Output:** `{"status": "ok|error", "session_id": "...", "message": "...", "content": "..."}`
- **Action:** Navigates to /feed/, clicks the "Start a post" button (`div[role="button"]`), locates the contenteditable editor (`div[contenteditable="true"][role="textbox"]`), and writes the content. Does **not** click Publish.

### `close_browser_tool`
- **Input:** `session_id` (string)
- **Output:** `{"status": "ok|error", "session_id": "...", "message": "..."}`
- **Action:** Closes the page and browser, stops the Playwright driver, and removes the session from memory. Cookies are discarded.

---

## Project Structure

```
linkedin-ai-agent/
├── agents/
│   └── linkedin_agent.md           # Agent definition (identity, safety rules)
├── mcp/
│   └── linkedin_server/
│       ├── __init__.py
│       ├── server.py               # MCP server (MCPServer, 5 tool bindings)
│       └── tools.py                # Core logic (Playwright automation)
├── src/
│   ├── core/
│   │   ├── agent_runner.py         # Placeholder
│   │   └── config.py               # Pydantic settings (ZAI_API_KEY, env file)
│   ├── services/
│   │   └── linkedin_flow.py        # publish_post → create_post (MCP tools)
│   └── telemetry/
│       └── logger.py               # Logging setup
├── tests/
│   ├── test_mcp.py                 # 24 tests: MCP tools with mocked Playwright
│   ├── test_agent.py               # Agent definition + skill frontmatter
│   ├── test_config.py              # Settings: defaults + env vars
│   └── test_harness.py             # HITL file-signal harness
├── scripts/
│   ├── run.ps1                     # Windows launcher (loads .env → zai-key)
│   └── run.sh                      # Linux/macOS launcher (loads .env → zai-key)
├── .opencode/
│   └── skills/
│       └── linkedin-poster/
│           └── SKILL.md            # Auto-discovered skill for OpenCode
├── Dockerfile                      # MCP server image (Python + Chromium)
├── docker-compose.yml              # Compose service definition
├── opencode.jsonc                  # OpenCode configuration (MCP, agent, model)
├── pyproject.toml                  # Python dependencies and project metadata
├── conftest.py                     # Pytest path setup (root imports)
├── run_test_flow.py                # End-to-end flow test (direct tool calls)
├── .github/workflows/ci.yml        # CI pipeline (ruff + pytest + docker build)
└── .env.example                    # Environment variable template
```

---

## Prerequisites

- **Python** >= 3.11
- **Chromium** browser (installed via Playwright)
- **OpenCode** CLI (for agent-based execution) — optional, direct tool invocation works without it
- **ZAI API key** (free, from https://z.ai) if using the configured GLM model via OpenCode

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd linkedin-ai-agent

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install the package and development dependencies
pip install -e ".[dev]"

# 4. Install Chromium for Playwright
playwright install chromium
```

---

## Configuration

Copy `.env.example` to `.env` and set your ZAI API key:

```env
ZAI_API_KEY=your-key-here
LOG_LEVEL=INFO
```

---

## Docker (environment packaging)

Docker packages the MCP server with all dependencies for reproducible builds and CI validation. The HITL flow requires a visible browser on the host — use local execution for login, 2FA, and manual publishing.

### Build

```bash
docker compose build
```

### Run (headless — no browser UI)

```bash
docker compose run --rm linkedin-mcp-server
```

This starts the MCP server in stdio mode. It validates that all dependencies resolve and the server starts correctly.

### What the image includes

| Component | Detail |
|---|---|
| Base image | `python:3.11-slim` |
| System deps | `libnss3`, `libnspr4`, `libatk1.0-0`, `libcups2`, `libdrm2`, `libgbm1`, etc. (Playwright Chromium requirements) |
| Python deps | Installed from `pyproject.toml` via `pip install -e ".[dev]"` |
| Chromium | Installed via `playwright install chromium` |

---

## Execution

### Ejecutar el agente

```bash
# 1. Copiar el archivo de ejemplo
cp .env.example .env

# 2. Editar .env y poner tu API key de ZAI (https://z.ai):
#    ZAI_API_KEY=tu-key-aqui

# 3. Ejecutar:
./scripts/run.sh "Crea un post en LinkedIn diciendo Hola mundo"   # Linux / macOS
.\scripts\run.ps1 "Crea un post en LinkedIn diciendo Hola mundo"  # Windows
```

El script lee la key de `.env`, la escribe en `.opencode/zai-key`, y ejecuta `opencode run --agent linkedin-agent` con tu instrucción. No necesitas exportar nada manualmente.

### Test / demo flow (direct tool calls)

For quick verification of the browser automation pipeline:

```bash
python run_test_flow.py
```

This script calls MCP tools directly (agent bypass) and uses a `.hitl_signal` file for HITL confirmation — suitable for testing and CI.

### Agent flow (via OpenCode conversation — real HITL)

The production flow uses OpenCode's conversational interface. HITL confirmation happens through chat, not file signals.

Usa los scripts de `scripts/` para cargar `.env` automáticamente (ver [Ejecutar el agente](#ejecutar-el-agente)):

```bash
./scripts/run.sh "Write a post about AI trends"
```

O manualmente (requiere la key en `.opencode/zai-key`):

```bash
opencode
# Then prompt: @linkedin-agent "Write a post about AI trends"
```

The agent orchestrates the full flow:
1. Requests content, validates, shows preview, asks for confirmation via chat
2. Opens the browser, the user logs in manually (visible browser)
3. Writes content in the editor, then asks via chat for final approval
4. The user clicks "Post" manually in the browser and confirms in chat
5. The agent closes the browser

### Via MCP server (stdio)

```bash
python -m mcp.linkedin_server.server
```

The server listens on stdin/stdout and can be connected by any MCP client. Tools are invoked via the standard MCP request/response protocol.

---

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_mcp.py -v
```

**Current test coverage (33 tests):**

| Test file | Tests | Scope |
|---|---|---|
| `tests/test_mcp.py` | 24 | MCP tools with full Playwright mocking |
| `tests/test_agent.py` | 3 | Agent definition + skill frontmatter |
| `tests/test_config.py` | 2 | Settings defaults and env vars |
| `tests/test_harness.py` | 4 | HITL file-signal harness |

All MCP tool functions are tested with mocked `async_playwright`, covering success paths, error handling, and the full happy-path flow.

**CI pipeline (`.github/workflows/ci.yml`):** `ruff check .` → `pytest` → `docker build` (validates the MCP server image).

---

## Security Decisions

| Principle | Implementation |
|---|---|
| **No credential storage** | Credentials are never read, written, or logged by the agent. Login fields are never populated programmatically. |
| **No cookie persistence** | The browser context is ephemeral. Closing the browser via `close_browser_tool` discards all session cookies. No cookies are serialized to disk. |
| **No authentication bypass** | The agent never attempts to bypass login, 2FA, CAPTCHA, or any LinkedIn security mechanism. It only detects that authentication has occurred. |
| **Minimum privilege** | The agent only automates post creation. It does not modify profiles, send messages, manage connections, or perform any action beyond the publication flow. |
| **Audit logging** | A logger component is available in `src/telemetry/logger.py` for timestamped action records (credentials are never included). |
| **Session isolation** | Each run creates a fresh Playwright session. Session IDs are UUIDs held only in memory. Consecutive runs have no shared state. |

---

## Limitations

| Limitation | Description | Potential improvement |
|---|---|---|
| **No session persistence** | Sessions are in-memory only. If the MCP connection drops, the browser closes. | Implement browser context serialization or a long-running server with keepalive. |
| **Locale-dependent selectors** | The "Start a post" button selector targets Spanish text (`name="Crear"`). Fails on English or other locales. | Use ARIA role selectors or detect locale from page metadata. |
| **`src/core/agent_runner.py`** | Empty placeholder. | Implement the runner that bridges the OpenCode agent to the MCP tools. |
| **No CI e2e test** | The CI workflow only runs unit tests with mocks. Real Playwright tests require a display server. | Add a CI job with `xvfb` for headful Playwright in CI. |
| **No image/video support** | Currently only plain text posts. | Extend `create_post_tool` to handle media uploads through the LinkedIn editor. |
| **Error recovery** | If the user closes the browser tab mid-flow, the tool returns an error and exits. | Add browser crash detection and session recovery logic. |
| **LinkedIn DOM changes** | Selectors (`div[role="button"]`, `div[contenteditable="true"]`) may break if LinkedIn updates its UI. | Add a selector health-check tool and fallback strategies. |

---

## License

MIT
