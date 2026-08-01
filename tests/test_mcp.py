from unittest.mock import AsyncMock, MagicMock, patch

import playwright.async_api as pw
import pytest

from mcp.linkedin_server.tools import (
    SessionManager,
    close_browser,
    create_post,
    open_browser,
    sessions,
    verify_active_session,
    wait_for_human_auth,
)


@pytest.fixture(autouse=True)
def reset_sessions():
    """Limpia el dict de sesiones antes de cada test."""
    sessions._sessions.clear()
    yield
    sessions._sessions.clear()


@pytest.fixture
def mock_playwright():
    """Mockea toda la API asíncrona de Playwright."""
    mock_page = AsyncMock()
    mock_page.url = "https://www.linkedin.com/login"
    mock_page.keyboard = MagicMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.on = MagicMock()
    mock_page.viewport_size = AsyncMock(return_value={"width": 1366, "height": 768})
    mock_page.set_viewport_size = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value={"w": 1366, "h": 768})

    def make_locator():
        loc = AsyncMock()
        loc.wait_for = AsyncMock()
        loc.click = AsyncMock()
        loc.fill = AsyncMock()
        loc.filter = MagicMock(return_value=loc)
        loc.locator = MagicMock(return_value=loc)
        return loc

    locators = {}

    def get_locator(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        if key not in locators:
            locators[key] = make_locator()
        return locators[key]

    mock_page.locator = MagicMock(side_effect=get_locator)
    mock_page.get_by_role = MagicMock(side_effect=get_locator)

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_playwright_obj = AsyncMock()
    mock_playwright_obj.chromium = mock_chromium

    mock_playwright_class = AsyncMock()
    mock_playwright_class.start = AsyncMock(return_value=mock_playwright_obj)

    return mock_page, mock_browser, mock_chromium, mock_playwright_class


@pytest.fixture
def patched_playwright(mock_playwright):
    mock_page, mock_browser, _, mock_playwright_class = mock_playwright
    with patch("playwright.async_api.async_playwright", return_value=mock_playwright_class):
        yield mock_page, mock_browser


class TestSessionManager:
    def test_create_session(self):
        sm = SessionManager()
        session = sm.create_session()
        assert session.session_id in sm._sessions
        assert session.is_authenticated is False
        assert session._post_content == ""

    def test_get_session(self):
        sm = SessionManager()
        created = sm.create_session()
        retrieved = sm.get_session(created.session_id)
        assert retrieved is created

    def test_get_session_not_found(self):
        sm = SessionManager()
        assert sm.get_session("nonexistent") is None

    def test_remove_session(self):
        sm = SessionManager()
        session = sm.create_session()
        sm.remove_session(session.session_id)
        assert sm.get_session(session.session_id) is None


class TestOpenBrowser:
    @pytest.mark.asyncio
    async def test_open_browser_new_session(self, patched_playwright):
        result = await open_browser()

        assert result["status"] == "ok"
        assert "session_id" in result
        assert len(sessions._sessions) == 1

    @pytest.mark.asyncio
    async def test_open_browser_with_session_id(self, patched_playwright):
        pre = sessions.create_session()

        result = await open_browser(session_id=pre.session_id)

        assert result["status"] == "ok"
        assert result["session_id"] == pre.session_id

    @pytest.mark.asyncio
    async def test_open_browser_tracks_popups(self, patched_playwright):
        mock_page, _ = patched_playwright
        await open_browser()

        handler = mock_page.on.call_args[0][1]
        popup = MagicMock()
        handler(popup)

        session = next(iter(sessions._sessions.values()))
        assert session.popup_pages == [popup]

    @pytest.mark.asyncio
    async def test_open_browser_failure(self, patched_playwright):
        with patch(
            "playwright.async_api.async_playwright",
            side_effect=RuntimeError("No browser"),
        ):
            result = await open_browser()
            assert result["status"] == "error"
            assert "No browser" in result["message"]


class TestWaitForHumanAuth:
    @pytest.mark.asyncio
    async def test_session_not_found(self):
        result = await wait_for_human_auth("ghost")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_no_page(self):
        session = sessions.create_session()
        result = await wait_for_human_auth(session.session_id)
        assert result["status"] == "error"
        assert "No browser page" in result["message"]

    @pytest.mark.asyncio
    async def test_already_authenticated(self, patched_playwright):
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True

        result = await wait_for_human_auth(session.session_id)
        assert result["status"] == "ok"
        assert "Already authenticated" in result["message"]

    @pytest.mark.asyncio
    async def test_authentication_success(self, patched_playwright):
        mock_page, _ = patched_playwright
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        mock_page.url = "https://www.linkedin.com/feed/"

        result = await wait_for_human_auth(session.session_id, timeout_minutes=1, poll_seconds=1)
        assert result["status"] == "ok"
        assert session.is_authenticated is True

    @pytest.mark.asyncio
    async def test_authentication_success_via_checkpoint_popup(self, patched_playwright):
        mock_page, _ = patched_playwright
        await open_browser()
        session = next(iter(sessions._sessions.values()))

        handler = mock_page.on.call_args[0][1]
        popup = MagicMock()
        popup.url = "https://www.linkedin.com/checkpoint/challenges"
        handler(popup)

        result = await wait_for_human_auth(session.session_id, timeout_minutes=1, poll_seconds=1)
        assert result["status"] == "ok"
        assert session.is_authenticated is True

    @pytest.mark.asyncio
    async def test_authentication_timeout(self, patched_playwright):
        mock_page, _ = patched_playwright
        mock_page.url = "https://www.linkedin.com/login"
        await open_browser()
        session = next(iter(sessions._sessions.values()))

        result = await wait_for_human_auth(session.session_id, timeout_minutes=0, poll_seconds=1)
        assert result["status"] == "error"
        assert "timeout" in result["message"].lower()


class TestVerifyActiveSession:
    @pytest.mark.asyncio
    async def test_session_not_found(self):
        result = await verify_active_session("ghost")
        assert result["active"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_no_page(self):
        session = sessions.create_session()
        result = await verify_active_session(session.session_id)
        assert result["active"] is False

    @pytest.mark.asyncio
    async def test_not_authenticated(self, patched_playwright):
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = False

        result = await verify_active_session(session.session_id)
        assert result["active"] is False

    @pytest.mark.asyncio
    async def test_session_active(self, patched_playwright):
        mock_page, _ = patched_playwright
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True
        mock_page.url = "https://www.linkedin.com/feed/"

        result = await verify_active_session(session.session_id)
        assert result["active"] is True

    @pytest.mark.asyncio
    async def test_session_expired(self, patched_playwright):
        mock_page, _ = patched_playwright
        mock_page.url = "https://www.linkedin.com/login"
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True

        result = await verify_active_session(session.session_id)
        assert result["active"] is False


class TestCreatePost:
    @pytest.mark.asyncio
    async def test_session_not_found(self):
        result = await create_post("ghost", "Hello")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_no_page(self):
        session = sessions.create_session()
        result = await create_post(session.session_id, "Hello")
        assert result["status"] == "error"
        assert "No browser page" in result["message"]

    @pytest.mark.asyncio
    async def test_not_authenticated(self, patched_playwright):
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        result = await create_post(session.session_id, "Hello")
        assert result["status"] == "error"
        assert "Not authenticated" in result["message"]

    @pytest.mark.asyncio
    async def test_create_post_success(self, patched_playwright):
        mock_page, _ = patched_playwright
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True

        result = await create_post(session.session_id, "Test post content")
        assert result["status"] == "ok"
        assert session._post_content == "Test post content"
        assert session._published is True

        # Flujo principal: /feed/ + disparador + etiqueta de publicar
        feed_calls = [c.args[0] for c in mock_page.goto.await_args_list]
        assert any("/feed/" in url for url in feed_calls)
        trigger = mock_page.get_by_role("button", name="Crear")
        assert trigger.click.await_count == 1
        publish = mock_page.get_by_role("button", name="Publicar", exact=True).last
        assert publish.click.await_count == 1
        # Solo se presiona Escape para cerrar modales; nunca el atajo de publicar
        keys = [c.args[0] for c in mock_page.keyboard.press.await_args_list]
        assert keys == ["Escape"]

    @pytest.mark.asyncio
    async def test_create_post_falls_back_to_direct_url(self, patched_playwright):
        mock_page, _ = patched_playwright
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True

        # El disparador de /feed/ no responde (ni etiquetas ni clases)
        for label in ("Crear", "Start a post", "Poster", "Publier", "Commencer"):
            mock_page.get_by_role("button", name=label).wait_for.side_effect = pw.TimeoutError("no trigger")
        for selector in ("button.share-box-feed-entry__trigger", "div.share-box-feed-entry__trigger"):
            mock_page.locator(selector).first.wait_for.side_effect = pw.TimeoutError("no trigger")

        result = await create_post(session.session_id, "Test post content")
        assert result["status"] == "ok"

        # Camino de respaldo: URL directa del composer
        composer_calls = [c.args[0] for c in mock_page.goto.await_args_list]
        assert any("post/new" in url for url in composer_calls)

    @pytest.mark.asyncio
    async def test_create_post_all_publish_strategies_fail(self, patched_playwright):
        mock_page, _ = patched_playwright
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True

        # El composer nunca se cierra y no hay toast de éxito
        editor = mock_page.locator('div[contenteditable="true"][role="textbox"]')

        async def wait_for(**kwargs):
            if kwargs.get("state") == "detached":
                raise pw.TimeoutError("still open")

        editor.wait_for = AsyncMock(side_effect=wait_for)
        mock_page.locator(".artdeco-toast-message").first.wait_for.side_effect = pw.TimeoutError("no toast")
        mock_page.locator('div[role="alert"]').first.wait_for.side_effect = pw.TimeoutError("no toast")
        # El atajo de teclado (último recurso) también falla
        mock_page.keyboard.press = AsyncMock(side_effect=RuntimeError("keyboard blocked"))

        result = await create_post(session.session_id, "Test post content")

        assert result["status"] == "error"
        assert "Could not publish" in result["message"]
        assert session._published is False

    @pytest.mark.asyncio
    async def test_create_post_uses_fit_viewport(self, patched_playwright):
        mock_page, _ = patched_playwright
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True

        # El viewport se calcula restando márgenes a la pantalla (1366x768 -> 1346x708)
        assert session.viewport_size == {"width": 1346, "height": 708}

        result = await create_post(session.session_id, "Test post content")

        assert result["status"] == "ok"
        last_call = mock_page.set_viewport_size.await_args_list[-1]
        assert last_call.args[0] == {"width": 1346, "height": 708}


class TestCloseBrowser:
    @pytest.mark.asyncio
    async def test_close_nonexistent(self):
        result = await close_browser("ghost")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_close_browser_ok(self, patched_playwright):
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True

        result = await close_browser(session.session_id)
        assert result["status"] == "ok"
        assert sessions.get_session(session.session_id) is None


class TestFullFlow:
    @pytest.mark.asyncio
    async def test_full_happy_path(self, patched_playwright):
        mock_page, _ = patched_playwright

        # 1. Abrir navegador
        open_result = await open_browser()
        assert open_result["status"] == "ok"
        sid = open_result["session_id"]

        # 2. Autenticar
        mock_page.url = "https://www.linkedin.com/feed/"
        auth_result = await wait_for_human_auth(sid, timeout_minutes=1, poll_seconds=1)
        assert auth_result["status"] == "ok"

        # 3. Verificar sesión
        verify_result = await verify_active_session(sid)
        assert verify_result["active"] is True

        # 4. Crear post
        post_result = await create_post(sid, "Hello World")
        assert post_result["status"] == "ok"
        session = next(iter(sessions._sessions.values()))
        assert session._published is True

        # 5. Cerrar navegador
        close_result = await close_browser(sid)
        assert close_result["status"] == "ok"
