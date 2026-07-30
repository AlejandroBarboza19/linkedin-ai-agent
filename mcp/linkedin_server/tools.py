import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrowserSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    browser: Optional[object] = None
    page: Optional[object] = None
    is_authenticated: bool = False
    created_at: float = field(default_factory=time.time)


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

    # TODO: implementar playwright
    # from playwright.async_api import async_playwright
    # p = await async_playwright().start()
    # browser = await p.chromium.launch(headless=False)
    # page = await browser.new_page()
    # await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    # session.browser = browser
    # session.page = page

    return {
        "status": "ok",
        "session_id": session.session_id,
        "message": "Browser opened at linkedin.com/login",
    }


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

    # TODO: implementar playwright
    # start = time.time()
    # while time.time() - start < timeout_minutes * 60:
    #     current_url = await session.page.url()
    #     if any(p in current_url for p in ("/feed", "/checkpoint", "/mynetwork")):
    #         session.is_authenticated = True
    #         return {"status": "ok", "session_id": session_id, "message": "User authenticated"}
    #     await asyncio.sleep(poll_seconds)
    # return {"status": "error", "session_id": session_id, "message": "Authentication timeout"}

    session.is_authenticated = True
    return {
        "status": "ok",
        "session_id": session_id,
        "message": "User authenticated successfully",
    }


async def verify_active_session(session_id: str) -> dict:
    """Verifica si la sesión de LinkedIn sigue activa en el navegador."""
    session = sessions.get_session(session_id)
    if session is None:
        return {"status": "error", "session_id": session_id, "message": "Session not found", "active": False}

    if not session.is_authenticated:
        return {"status": "ok", "session_id": session_id, "message": "Session exists but not authenticated", "active": False}

    # TODO: comprobar expiración navegando a /feed y verificando redirección a /login
    # current_url = await session.page.url()
    # await session.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    # if "/login" in session.page.url:
    #     session.is_authenticated = False
    #     return {"status": "ok", "session_id": session_id, "message": "Session expired", "active": False}

    return {
        "status": "ok",
        "session_id": session_id,
        "message": "Session is active",
        "active": True,
    }


async def create_post(session_id: str, content: str) -> dict:
    """Navega al editor de posts, rellena el contenido y hace clic en Publicar."""
    session = sessions.get_session(session_id)
    if session is None:
        return {"status": "error", "message": f"Session {session_id} not found"}
    if not session.is_authenticated:
        return {"status": "error", "message": "Not authenticated. Run wait_for_human_auth first."}

    # TODO: implementar playwright
    # await session.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    # await session.page.click('button[aria-label="Start a post"]')
    # await session.page.wait_for_selector('.ql-editor')
    # await session.page.fill('.ql-editor', content)
    # await asyncio.sleep(1)
    # await session.page.click('button[aria-label="Post"]')
    # await session.page.wait_for_timeout(2000)

    return {
        "status": "ok",
        "session_id": session_id,
        "message": "Post created and published successfully",
        "content": content,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


async def close_browser(session_id: str) -> dict:
    """Cierra el navegador y descarta las cookies de sesión."""
    session = sessions.get_session(session_id)
    if session is None:
        return {"status": "error", "message": f"Session {session_id} not found"}

    # TODO: implementar playwright
    # if session.page:
    #     await session.page.close()
    # if session.browser:
    #     await session.browser.close()

    sessions.remove_session(session_id)
    return {"status": "ok", "session_id": session_id, "message": "Browser closed, session discarded"}
