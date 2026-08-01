import asyncio
import time
import uuid
from dataclasses import dataclass, field

import playwright.async_api as pw

from src.telemetry.logger import logger


@dataclass
class BrowserSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    playwright: object | None = None
    browser: object | None = None
    page: object | None = None
    is_authenticated: bool = False
    created_at: float = field(default_factory=time.time)
    _post_content: str = ""
    _published: bool = False
    popup_pages: list = field(default_factory=list)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, BrowserSession] = {}

    def create_session(self) -> BrowserSession:
        session = BrowserSession()
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> BrowserSession | None:
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


sessions = SessionManager()

# URLs/selectores que indican que una ventana emergente pertenece al flujo
# de autenticación y NO debe cerrarse automáticamente.
_AUTH_POPUP_KEYWORDS = ("checkpoint", "feed", "authwall")

# Selectores de botones de cierre para modales/upsells in-page (Premium, cookies).
_CLOSE_BUTTON_SELECTORS = (
    'button[aria-label="Dismiss"]',
    'button[aria-label="Close"]',
    'button[aria-label="Cerrar"]',
    ".artdeco-modal__dismiss",
)


async def _dismiss_inpage_modals(session: BrowserSession) -> None:
    """Cierra modales/upsells in-page (Premium/Plus, cookies) de forma segura.

    Solo presiona Escape e intenta botones de cierre explícitos. Nunca toca
    elementos de autenticación ni confirma diálogos.
    """
    page = session.page
    if page is None:
        return
    try:
        await page.keyboard.press("Escape")
    except Exception as e:
        logger.debug("Escape dismiss failed: %s", e)
    for selector in _CLOSE_BUTTON_SELECTORS:
        try:
            btn = page.locator(selector).first
            await btn.wait_for(state="visible", timeout=800)
            await btn.click()
            break
        except Exception as e:
            logger.debug("No dismiss button %s: %s", selector, e)


def _is_auth_popup(url: str) -> bool:
    """True si la URL de la ventana emergente pertenece al flujo de login."""
    return any(keyword in url for keyword in _AUTH_POPUP_KEYWORDS)


async def open_browser(session_id: str | None = None) -> dict:
    """Abre un navegador visible (no headless) con Playwright y navega a linkedin.com/login."""
    session = sessions.create_session() if session_id is None else sessions.get_session(session_id)
    if session is None:
        session = sessions.create_session()

    try:
        p = await pw.async_playwright().start()
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        def _track_popup(popup: pw.Page) -> None:
            session.popup_pages.append(popup)

        page.on("popup", _track_popup)
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
            popup_urls = [p.url for p in session.popup_pages if p.url]
            if "/login" not in current_url or any(_is_auth_popup(u) for u in popup_urls):
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
    except pw.TimeoutError:
        session.is_authenticated = False
        return {"status": "error", "session_id": session_id, "message": "Page load timeout. Session may be expired.", "active": False}
    except Exception as e:
        return {"status": "error", "session_id": session_id, "message": f"Error verifying session: {e}", "active": False}


async def create_post(session_id: str, content: str) -> dict:
    """Navega al feed de LinkedIn, abre el editor, escribe el contenido y publica.

    El clic en "Publicar" se ejecuta automáticamente. El HITL queda reservado
    para el login y 2FA, que el usuario completa manualmente en el navegador.
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

        # Cerrar modales/upsells in-page (Premium/Plus, cookies) que puedan
        # interceptar los clics sobre el editor de posts.
        await _dismiss_inpage_modals(session)

        # Click en el botón "Start a post" (varía según el locale)
        create_btn = session.page.get_by_role("button", name="Crear")
        try:
            await create_btn.wait_for(timeout=5000)
        except Exception:
            # Fallback: intentar locale en inglés o selector genérico
            create_btn = session.page.locator('div[role="button"]').filter(has_text="Crear")
            await create_btn.wait_for(timeout=5000)
        await create_btn.click()

        await asyncio.sleep(1)

        # Buscar el editor (div contenteditable dentro del modal de post)
        editor = session.page.locator('div[contenteditable="true"][role="textbox"]')
        try:
            await editor.wait_for(timeout=5000)
        except Exception:
            editor = session.page.locator('div[role="textbox"]')
            await editor.wait_for(timeout=5000)
        await editor.fill(content)

        # Click en el botón de publicar automáticamente (la etiqueta varía según el locale)
        publish_btn = None
        for label in ("Publicar", "Post"):
            candidate = session.page.get_by_role("button", name=label, exact=True)
            try:
                await candidate.wait_for(timeout=3000)
            except pw.TimeoutError:
                publish_btn = None
            else:
                publish_btn = candidate
                break
        if publish_btn is None:
            return {
                "status": "error",
                "session_id": session_id,
                "message": "Editor filled but publish button not found. Locale may have changed.",
            }

        await publish_btn.click()

        # Esperar a que el modal del editor se cierre, confirmando la publicación
        try:
            await editor.wait_for(state="detached", timeout=10000)
        except pw.TimeoutError:
            logger.warning("Composer modal did not close in time after publishing")

        session._post_content = content
        session._published = True

        return {
            "status": "ok",
            "session_id": session_id,
            "message": "Post published successfully.",
            "content": content,
        }
    except pw.TimeoutError:
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
