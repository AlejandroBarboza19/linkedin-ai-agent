import asyncio
import sys
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


# Tamaño mínimo de ventana en el que LinkedIn muestra todos los controles del
# editor. Con una ventana más pequeña el layout responsivo oculta botones.
_MIN_VIEWPORT_SIZE = {"width": 1280, "height": 800}


async def _ensure_reasonable_viewport(session: BrowserSession) -> bool:
    """Si la ventana del navegador es demasiado pequeña, la agranda.

    LinkedIn usa layouts responsivos: con una ventana muy pequeña el botón
    para crear el post puede ocultarse y los selectores fallan. Es best-effort:
    si el ajuste no se puede aplicar, devuelve False y el flujo continúa.
    Devuelve True si se agrandó la ventana.
    """
    page = session.page
    if page is None:
        return False
    try:
        vp = await page.viewport_size()
        if vp and (
            vp["width"] < _MIN_VIEWPORT_SIZE["width"]
            or vp["height"] < _MIN_VIEWPORT_SIZE["height"]
        ):
            await page.set_viewport_size(_MIN_VIEWPORT_SIZE)
            await asyncio.sleep(1)
            return True
    except Exception as e:
        logger.debug("Viewport resize failed: %s", e)
    return False


# ─────────────────────────────────────────────────────────────────────────
# Publicación robusta: estrategias en cascada para no depender del locale
# ni del estado del DOM de LinkedIn.
# ─────────────────────────────────────────────────────────────────────────

# URL directa del editor de posts: abre el composer sin depender del botón
# "Start a post" (que cambia de etiqueta según el idioma).
_COMPOSER_URL = "https://www.linkedin.com/post/new/"
_FEED_URL = "https://www.linkedin.com/feed/"

# Editor del post: selectores por rol ARIA (independientes del idioma).
_EDITOR_SELECTOR = 'div[contenteditable="true"][role="textbox"]'
_EDITOR_FALLBACK = 'div[role="textbox"]'

# Disparador del composer en /feed/ (clases estables de LinkedIn + etiquetas
# multi-locale como último recurso).
_TRIGGER_SELECTORS = (
    "button.share-box-feed-entry__trigger",
    "div.share-box-feed-entry__trigger",
)
_TRIGGER_LABELS = ("Crear", "Start a post", "Poster", "Publier", "Commencer")

# Botón de publicar: clase estable (independiente del idioma) + etiquetas.
_PUBLISH_PRIMARY_SELECTOR = 'div[role="dialog"] button.artdeco-button--primary'
_PUBLISH_LABELS = ("Publicar", "Post", "Publish", "Publier")

# Indicadores de publicación exitosa (toast de confirmación).
_SUCCESS_TOAST_SELECTORS = (
    ".artdeco-toast-message",
    'div[role="alert"]',
)


async def _get_editor(page) -> object:
    """Devuelve el editor contenteditable del composer, con fallback por rol."""
    editor = page.locator(_EDITOR_SELECTOR)
    try:
        await editor.wait_for(timeout=3000)
        return editor
    except pw.TimeoutError:
        fallback = page.locator(_EDITOR_FALLBACK)
        await fallback.wait_for(timeout=3000)
        return fallback


async def _click_trigger(page) -> bool:
    """Abre el composer desde /feed/ haciendo clic en el disparador del post.

    Prueba selectores por clase (estables), luego etiquetas multi-locale.
    Devuelve True si logró abrir el editor.
    """
    for selector in _TRIGGER_SELECTORS:
        try:
            loc = page.locator(selector).first
            await loc.wait_for(state="visible", timeout=2000)
            await loc.click()
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.debug("Trigger selector %s failed: %s", selector, e)
            continue
    for label in _TRIGGER_LABELS:
        try:
            loc = page.get_by_role("button", name=label)
            await loc.wait_for(state="visible", timeout=2000)
            await loc.click()
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.debug("Trigger label %s failed: %s", label, e)
            continue
    return False


async def _open_composer(session: BrowserSession) -> bool:
    """Abre el editor de posts con estrategias en cascada.

    1. URL directa del composer (independiente del DOM/botones).
    2. /feed/ + clic en el disparador (selectores de clase + etiquetas).

    Devuelve True si el editor quedó visible.
    """
    page = session.page
    if page is None:
        return False

    try:
        await page.goto(_COMPOSER_URL, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        logger.debug("Direct composer URL failed: %s", e)
    else:
        await asyncio.sleep(2)
        try:
            await page.locator(_EDITOR_SELECTOR).wait_for(state="visible", timeout=3000)
            return True
        except pw.TimeoutError:
            logger.debug("Composer not present on direct URL, falling back to feed trigger")

    try:
        await page.goto(_FEED_URL, wait_until="load", timeout=30000)
        await asyncio.sleep(2)
    except Exception as e:
        logger.debug("Feed navigation failed: %s", e)

    await _dismiss_inpage_modals(session)
    return await _click_trigger(page)


async def _publish_succeeded(page, editor) -> bool:
    """Confirma si la publicación se completó (composer cerrado o toast)."""
    try:
        await editor.wait_for(state="detached", timeout=5000)
        return True
    except pw.TimeoutError:
        pass
    for selector in _SUCCESS_TOAST_SELECTORS:
        try:
            await page.locator(selector).first.wait_for(state="visible", timeout=1500)
            return True
        except Exception as e:
            logger.debug("Toast selector %s not found: %s", selector, e)
            continue
    return False


async def _publish_post(page, editor) -> bool:
    """Publica con estrategias en cascada hasta que una confirme éxito.

    1. Botón primario del modal (clase estable, independiente del idioma).
    2. Etiquetas de botón multi-locale.
    3. Atajo de teclado Ctrl/Cmd+Enter (funciona con cualquier UI).
    """
    primary = page.locator(_PUBLISH_PRIMARY_SELECTOR).first
    try:
        await primary.wait_for(state="visible", timeout=3000)
        await primary.click()
        if await _publish_succeeded(page, editor):
            return True
    except Exception as e:
        logger.debug("Primary publish button failed: %s", e)

    for label in _PUBLISH_LABELS:
        candidate = page.get_by_role("button", name=label, exact=True)
        try:
            await candidate.wait_for(state="visible", timeout=2000)
        except pw.TimeoutError:
            continue
        await candidate.click()
        if await _publish_succeeded(page, editor):
            return True

    key = "Meta+Enter" if sys.platform == "darwin" else "Control+Enter"
    try:
        await editor.click()
        await page.keyboard.press(key)
        if await _publish_succeeded(page, editor):
            return True
    except Exception as e:
        logger.debug("Keyboard publish failed: %s", e)
    return False


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
    """Abre el editor de LinkedIn, escribe el contenido y publica.

    Usa estrategias en cascada para publicar sin importar el locale ni el
    estado del DOM de LinkedIn:
      1. Abre el editor directamente por URL (linkedin.com/post/new/).
      2. Si no abre, va a /feed/ y hace clic en el disparador del post
         (selectores por clase estables + etiquetas multi-locale).
      3. Publica con el botón primario del modal (independiente del idioma),
         o por etiqueta, o con el atajo Ctrl/Cmd+Enter (último recurso).

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
        # Ventana suficientemente grande para que LinkedIn muestre los controles
        # del editor (los layouts responsivos ocultan botones en ventanas pequeñas).
        await _ensure_reasonable_viewport(session)

        if not await _open_composer(session):
            return {
                "status": "error",
                "session_id": session_id,
                "message": (
                    "Could not open the post composer. Restore the browser to normal "
                    "size (maximize the window) and try again."
                ),
            }

        editor = await _get_editor(session.page)
        await editor.fill(content)

        if not await _publish_post(session.page, editor):
            return {
                "status": "error",
                "session_id": session_id,
                "message": (
                    "Could not publish the post. Restore the browser to normal size "
                    "(maximize the window) and try again."
                ),
            }

        session._post_content = content
        session._published = True

        return {
            "status": "ok",
            "session_id": session_id,
            "message": "Post published successfully.",
            "content": content,
        }
    except pw.TimeoutError:
        return {
            "status": "error",
            "session_id": session_id,
            "message": (
                "Timeout waiting for editor elements. Restore the browser to normal "
                "size (maximize the window) or reload the feed and retry."
            ),
        }
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
