from mcp.server.fastmcp import FastMCP

from .tools import (
    open_browser,
    wait_for_human_auth,
    verify_active_session,
    create_post,
    close_browser,
)

mcp = FastMCP(
    "linkedin_server",
    instructions=(
        "LinkedIn automation server using Playwright (visible browser). "
        "Flujo: open_browser → wait_for_human_auth → create_post → close_browser. "
        "El usuario debe hacer login y 2FA manualmente en el navegador."
    ),
)


@mcp.tool()
async def open_browser_tool(session_id: str = "") -> dict:
    """Abre un navegador visible (no headless) en linkedin.com/login. Devuelve un session_id para operaciones posteriores."""
    return await open_browser(session_id or None)


@mcp.tool()
async def wait_for_human_auth_tool(session_id: str, timeout_minutes: int = 5) -> dict:
    """Espera a que el usuario haga login y resuelva 2FA manualmente en el navegador visible."""
    return await wait_for_human_auth(session_id, timeout_minutes)


@mcp.tool()
async def verify_session_tool(session_id: str) -> dict:
    """Verifica si la sesión de LinkedIn sigue activa."""
    return await verify_active_session(session_id)


@mcp.tool()
async def create_post_tool(session_id: str, content: str) -> dict:
    """Rellena el contenido en el editor de LinkedIn y publica el post."""
    return await create_post(session_id, content)


@mcp.tool()
async def close_browser_tool(session_id: str) -> dict:
    """Cierra el navegador y descarta las cookies de sesión."""
    return await close_browser(session_id)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
