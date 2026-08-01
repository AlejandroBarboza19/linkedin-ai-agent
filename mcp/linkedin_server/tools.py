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
    viewport_size: dict | None = None


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


# Viewport preferido para el layout de escritorio de LinkedIn. El layout
# responsivo de LinkedIn usa el viewport de la página (CSS), NO el tamaño
# físico de la ventana del sistema. Se prefiere un viewport ajustado a la
# pantalla real (ver _fit_viewport) para que la ventana nunca quede recortada.
_MIN_VIEWPORT_SIZE = {"width": 1280, "height": 800}

# Viewport seguro por defecto si no se puede leer el tamaño de la pantalla:
# pequeño para que quepa en cualquier pantalla (el login siempre es accesible).
_SAFE_VIEWPORT_SIZE = {"width": 1100, "height": 700}


async def _fit_viewport(page) -> dict:
    """Calcula un viewport que quepa en la pantalla del usuario.

    Si la ventana del navegador es más grande que la pantalla, queda recortada
    y los botones (login, publicar) se vuelven inaccesibles. Se deja un margen
    para el marco de la ventana y la barra de tareas. Si no se puede leer la
    pantalla, se usa un tamaño seguro pequeño.
    """
    try:
        dims = await page.evaluate("() => ({w: screen.availWidth, h: screen.availHeight})")
        avail_w = int(dims.get("w") or _SAFE_VIEWPORT_SIZE["width"])
        avail_h = int(dims.get("h") or _SAFE_VIEWPORT_SIZE["height"])
    except Exception as e:
        logger.debug("Screen size unavailable: %s", e)
        return dict(_SAFE_VIEWPORT_SIZE)
    width = min(1440, max(avail_w - 20, 640))
    height = min(900, max(avail_h - 60, 480))
    return {"width": width, "height": height}


async def _ensure_reasonable_viewport(session: BrowserSession) -> bool:
    """Fija el viewport calculado para la pantalla del usuario.

    LinkedIn decide qué controles mostrar según el viewport de la página.
    Aplicar el viewport ajustado a la pantalla garantiza que la ventana no
    quede recortada y que los botones del editor sean accesibles.
    """
    page = session.page
    if page is None:
        return False
    target = session.viewport_size or _MIN_VIEWPORT_SIZE
    try:
        await page.set_viewport_size(target)
        await asyncio.sleep(0.5)
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
# Se prueban también sin el alcance de diálogo, porque el composer a página
# completa de /post/new/ no usa div[role="dialog"].
_PUBLISH_PRIMARY_SELECTORS = (
    'div[role="dialog"] button.artdeco-button--primary',
    "button.artdeco-button--primary",
)
_PUBLISH_LABELS = ("Publicar", "Post", "Publish", "Publier")

# Indicadores de publicación exitosa (toast de confirmación).
_SUCCESS_TOAST_SELECTORS = (
    ".artdeco-toast-message",
    'div[role="alert"]',
)


async def _wait_for_editor(page, timeout: int = 4000) -> bool:
    """Espera a que el editor del post esté visible (con fallback por rol)."""
    for selector in (_EDITOR_SELECTOR, _EDITOR_FALLBACK):
        try:
            await page.locator(selector).wait_for(state="visible", timeout=timeout)
            return True
        except pw.TimeoutError:
            continue
    return False


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

    Prueba etiquetas multi-locale primero (flujo que funcionó en ejecución
    real), luego selectores por clase (estables). Verifica que el editor
    quede visible antes de devolver éxito.
    """
    for label in _TRIGGER_LABELS:
        try:
            loc = page.get_by_role("button", name=label)
            await loc.wait_for(state="visible", timeout=2000)
            await loc.click()
            await asyncio.sleep(1)
            if await _wait_for_editor(page):
                return True
        except Exception as e:
            logger.debug("Trigger label %s failed: %s", label, e)
            continue
    for selector in _TRIGGER_SELECTORS:
        try:
            loc = page.locator(selector).first
            await loc.wait_for(state="visible", timeout=2000)
            await loc.click()
            await asyncio.sleep(1)
            if await _wait_for_editor(page):
                return True
        except Exception as e:
            logger.debug("Trigger selector %s failed: %s", selector, e)
            continue
    return False


async def _open_composer(session: BrowserSession) -> bool:
    """Abre el editor de posts con estrategias en cascada.

    1. /feed/ + clic en el disparador (flujo probado en ejecución real).
    2. URL directa del composer (independiente del DOM/botones).

    Devuelve True si el editor quedó visible.
    """
    page = session.page
    if page is None:
        return False

    try:
        await page.goto(_FEED_URL, wait_until="load", timeout=30000)
        await asyncio.sleep(2)
    except Exception as e:
        logger.debug("Feed navigation failed: %s", e)

    await _dismiss_inpage_modals(session)
    if await _click_trigger(page):
        return True

    try:
        await page.goto(_COMPOSER_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
    except Exception as e:
        logger.debug("Direct composer URL failed: %s", e)
        return False
    return await _wait_for_editor(page)


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

    1. Etiquetas de botón multi-locale (flujo probado en ejecución real),
       con coincidencia exacta y parcial.
    2. Botón primario (clase estable), en modal o a página completa.
    3. Atajo de teclado Ctrl/Cmd+Enter (funciona con cualquier UI).
    """
    for label in _PUBLISH_LABELS:
        for exact in (True, False):
            candidate = page.get_by_role("button", name=label, exact=exact).last
            try:
                await candidate.wait_for(state="visible", timeout=1500)
            except pw.TimeoutError:
                continue
            await candidate.click()
            if await _publish_succeeded(page, editor):
                return True

    for selector in _PUBLISH_PRIMARY_SELECTORS:
        loc = page.locator(selector).last
        try:
            await loc.wait_for(state="visible", timeout=2500)
            await loc.click()
            if await _publish_succeeded(page, editor):
                return True
        except Exception as e:
            logger.debug("Publish selector %s failed: %s", selector, e)

    key = "Meta+Enter" if sys.platform == "darwin" else "Control+Enter"
    try:
        await editor.focus()
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

        # Ventana ajustada a la pantalla: nunca recortada, login accesible.
        session.viewport_size = await _fit_viewport(page)
        try:
            await page.set_viewport_size(session.viewport_size)
        except Exception as e:
            logger.debug("Viewport fit failed: %s", e)

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
      1. Va a /feed/ y hace clic en el disparador del post (etiquetas
         multi-locale + selectores por clase estables), descartando modales
         in-page. Este flujo es el que funcionó en ejecución real.
      2. Si no abre, recurre a la URL directa del editor (post/new/).
      3. Publica por etiqueta ("Publicar"/"Post"/"Publish"/"Publier"),
         o con el botón primario (clase estable), o con el atajo
         Ctrl/Cmd+Enter (último recurso).

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
                    "Could not open the post composer (tried the feed trigger "
                    "and the direct composer URL). Check the browser window and retry."
                ),
            }

        editor = await _get_editor(session.page)
        await editor.fill(content)

        if not await _publish_post(session.page, editor):
            return {
                "status": "error",
                "session_id": session_id,
                "message": (
                    "Could not publish the post (tried the primary button, text "
                    "labels and Ctrl/Cmd+Enter). Check the browser window and retry."
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
                "Timeout waiting for the post editor. Reload the feed and retry."
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
