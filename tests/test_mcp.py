from unittest.mock import AsyncMock, MagicMock, patch

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
    """Clean sessions dict before each test."""
    sessions._sessions.clear()
    yield
    sessions._sessions.clear()


@pytest.fixture
def mock_playwright():
    """Mock the entire Playwright async API."""
    mock_page = AsyncMock()
    mock_page.url = "https://www.linkedin.com/login"

    def make_locator():
        loc = AsyncMock()
        loc.wait_for = AsyncMock()
        loc.click = AsyncMock()
        loc.fill = AsyncMock()
        loc.filter = MagicMock(return_value=loc)
        loc.locator = MagicMock(return_value=loc)
        return loc

    default_locator = make_locator()
    mock_page.locator = MagicMock(return_value=default_locator)
    mock_page.get_by_role = MagicMock(return_value=default_locator)

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
        await open_browser()
        session = next(iter(sessions._sessions.values()))
        session.is_authenticated = True

        result = await create_post(session.session_id, "Test post content")
        assert result["status"] == "ok"
        assert session._post_content == "Test post content"


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

        # 1. Open browser
        open_result = await open_browser()
        assert open_result["status"] == "ok"
        sid = open_result["session_id"]

        # 2. Authenticate
        mock_page.url = "https://www.linkedin.com/feed/"
        auth_result = await wait_for_human_auth(sid, timeout_minutes=1, poll_seconds=1)
        assert auth_result["status"] == "ok"

        # 3. Verify session
        verify_result = await verify_active_session(sid)
        assert verify_result["active"] is True

        # 4. Create post
        post_result = await create_post(sid, "Hello World")
        assert post_result["status"] == "ok"

        # 5. Close browser
        close_result = await close_browser(sid)
        assert close_result["status"] == "ok"
