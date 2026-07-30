import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


@dataclass
class BrowserSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    playwright: Optional[object] = None
    browser: Optional[object] = None
    page: Optional[object] = None
    is_authenticated: bool = False
    created_at: float = field(default_factory=time.time)
    _post_content: str = ""


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, BrowserSession] = {}

    def create_session(self) -> BrowserSession:
        session = BrowserSession()
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


sessions = SessionManager()


async def open_browser(session_id: str | None = None) -> dict:
    """Abre un navegador visible (no headless) con Playwright y navega a linkedin.com/login."""
    session = sessions.create_session() if session_id is None else sessions.get_session(session_id)
    if session is None:
        session = sessions.create_session()

    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        session.playwright = p
        session.browser = browser
        session.page = page

        return {
            "status": "ok",
            "session_id": session.session_id,
            "message": "Browser opened at linkedin.com/login",
        }
    except Exception as e:
        return {"status": "error", "session_id": session.session_id, "message": f"Failed to open browser: {e}"}


async def wait_for_human_auth(session_id: str, timeout_minutes: int = 5, poll_seconds: int = 2) -> dict:
    """Espera a que el usuario complete el login y 2FA manualmente en el navegador visible.

    Monitorea la URL cada `poll_seconds` segundos. Cuando detecta que la URL
    cambió de /login a /feed o /checkpoint, asume autenticación exitosa.
    """
    session = sessions.get_session(session_id)
    if session is None:
        return {"status": "error", "message": f"Session {session_id} not found"}

    if session.is_authenticated:
        return {"status": "ok", "message": "Already authenticated", "session_id": session_id}

    if session.page is None:
        return {"status": "error", "message": "No browser page. Run open_browser first.", "session_id": session_id}

    try:
        start = time.time()
        while time.time() - start < timeout_minutes * 60:
            current_url = session.page.url
            if "/login" not in current_url:
                session.is_authenticated = True
                return {
                    "status": "ok",
                    "session_id": session_id,
                    "message": "User authenticated successfully",
                }
            await asyncio.sleep(poll_seconds)

        return {
            "status": "error",
            "session_id": session_id,
            "message": "Authentication timeout. The user did not complete login in time.",
        }
    except Exception as e:
        return {"status": "error", "session_id": session_id, "message": f"Error while waiting for auth: {e}"}


async def verify_active_session(session_id: str) -> dict:
    """Verifica si la sesión de LinkedIn sigue activa en el navegador."""
    session = sessions.get_session(session_id)
    if session is None:
        return {"status": "error", "session_id": session_id, "message": "Session not found", "active": False}

    if session.page is None:
        return {"status": "error", "session_id": session_id, "message": "No browser page", "active": False}

    if not session.is_authenticated:
        return {"status": "ok", "session_id": session_id, "message": "Session exists but not authenticated", "active": False}

    try:
        current_url = session.page.url
        await session.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        final_url = session.page.url
        if "/login" in final_url or "login" in final_url.split("/"):
            session.is_authenticated = False
            return {"status": "ok", "session_id": session_id, "message": "Session expired", "active": False}

        return {
            "status": "ok",
            "session_id": session_id,
            "message": "Session is active",
            "active": True,
        }
    except PlaywrightTimeout:
        session.is_authenticated = False
        return {"status": "error", "session_id": session_id, "message": "Page load timeout. Session may be expired.", "active": False}
    except Exception as e:
        return {"status": "error", "session_id": session_id, "message": f"Error verifying session: {e}", "active": False}


async def create_post(session_id: str, content: str) -> dict:
    """Navega al feed de LinkedIn, abre el editor de posts y escribe el contenido.

    NOTA: El clic en Publicar requiere confirmación humana (HITL).
    Esta tool solo prepara el editor y deja el post listo para revisión.
    """
    session = sessions.get_session(session_id)
    if session is None:
        return {"status": "error", "message": f"Session {session_id} not found"}
    if session.page is None:
        return {"status": "error", "message": "No browser page. Run open_browser first."}
    if not session.is_authenticated:
        return {"status": "error", "message": "Not authenticated. Run wait_for_human_auth first."}

    try:
        await session.page.goto("https://www.linkedin.com/feed/", wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # Click the "Start a post" button (varies by locale)
        create_btn = session.page.get_by_role("button", name="Crear")
        try:
            await create_btn.wait_for(timeout=5000)
        except Exception:
            # Fallback: try English locale or generic selector
            create_btn = session.page.locator('div[role="button"]').filter(has_text="Crear")
            await create_btn.wait_for(timeout=5000)
        await create_btn.click()

        await asyncio.sleep(1)

        # Find the editor (contenteditable div inside the post modal)
        editor = session.page.locator('div[contenteditable="true"][role="textbox"]')
        try:
            await editor.wait_for(timeout=5000)
        except Exception:
            editor = session.page.locator('div[role="textbox"]')
            await editor.wait_for(timeout=5000)
        await editor.fill(content)

        session._post_content = content

        return {
            "status": "ok",
            "session_id": session_id,
            "message": "Editor opened and content written. User must review and click Publish manually.",
            "content": content,
        }
    except PlaywrightTimeout:
        return {"status": "error", "session_id": session_id, "message": "Timeout waiting for editor elements. LinkedIn page structure may have changed."}
    except Exception as e:
        return {"status": "error", "session_id": session_id, "message": f"Error creating post: {e}"}


async def close_browser(session_id: str) -> dict:
    """Cierra el navegador y descarta las cookies de sesión."""
    session = sessions.get_session(session_id)
    if session is None:
        return {"status": "error", "message": f"Session {session_id} not found"}

    try:
        if session.page is not None:
            await session.page.close()
        if session.browser is not None:
            await session.browser.close()
        if session.playwright is not None:
            await session.playwright.stop()
    except Exception as e:
        sessions.remove_session(session_id)
        return {"status": "error", "session_id": session_id, "message": f"Error closing browser: {e}"}

    sessions.remove_session(session_id)
    return {"status": "ok", "session_id": session_id, "message": "Browser closed, session discarded"}
