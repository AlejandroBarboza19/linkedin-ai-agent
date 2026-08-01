from mcp.server import MCPServer

from . import tools

server = MCPServer(
    "linkedin_server",
    instructions=(
        "Servidor de automatización de LinkedIn usando Playwright (navegador visible). "
        "Flujo: open_browser → wait_for_human_auth → create_post → close_browser. "
        "El usuario debe hacer login y 2FA manualmente en el navegador. "
        "La publicación del post es automática."
    ),
)


@server.tool(name="open_browser_tool", description="Abre un navegador visible (no headless) en linkedin.com/login. Devuelve un session_id.")
async def open_browser_tool(session_id: str = "") -> str:
    return str(await tools.open_browser(session_id or None))


@server.tool(
    name="wait_for_human_auth_tool",
    description="Espera a que el usuario haga login y resuelva 2FA manualmente en el navegador visible.",
)
async def wait_for_human_auth_tool(session_id: str, timeout_minutes: int = 5) -> str:
    return str(await tools.wait_for_human_auth(session_id, timeout_minutes))


@server.tool(
    name="verify_session_tool",
    description="Verifica si la sesión de LinkedIn sigue activa.",
)
async def verify_session_tool(session_id: str) -> str:
    return str(await tools.verify_active_session(session_id))


@server.tool(
    name="create_post_tool",
    description="Rellena el contenido en el editor de LinkedIn y publica el post automáticamente.",
)
async def create_post_tool(session_id: str, content: str) -> str:
    return str(await tools.create_post(session_id, content))


@server.tool(
    name="close_browser_tool",
    description="Cierra el navegador y descarta las cookies de sesión.",
)
async def close_browser_tool(session_id: str) -> str:
    return str(await tools.close_browser(session_id))


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
