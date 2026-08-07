from dataclasses import replace

import pytest

from genspark_cli.auth import (
    CapturedBrowserSession,
    _refresh_recaptcha_token,
    login_with_adapter,
)
from genspark_cli.exceptions import AuthenticationError
from genspark_cli.session import SessionManager


class FakeAdapter:
    def __init__(self, captured=None, error=None):
        self.captured = captured
        self.error = error
        self.calls = []

    async def capture(self, existing_state, headless):
        self.calls.append((existing_state, headless))
        if self.error:
            raise self.error
        return self.captured


def valid_capture():
    return CapturedBrowserSession(
        storage_state={
            "cookies": [{"name": "ai_session", "value": "browser-cookie"}]
        },
        recaptcha_token="browser-recaptcha",
    )


@pytest.mark.asyncio
async def test_login_persists_only_browser_session_material(tmp_path):
    session = SessionManager(str(tmp_path))
    adapter = FakeAdapter(valid_capture())

    assert await login_with_adapter(session, adapter, headless=False)
    assert adapter.calls == [(None, False)]
    assert session.get_cookies_dict()["ai_session"] == "browser-cookie"
    assert session.get_recaptcha_token() == "browser-recaptcha"

    combined = "".join(
        path.read_text() for path in tmp_path.glob("*") if path.is_file()
    )
    assert "api_key" not in combined.lower()


@pytest.mark.asyncio
async def test_login_passes_existing_storage_state_to_adapter(tmp_path):
    session = SessionManager(str(tmp_path))
    existing = {"cookies": [{"name": "ai_session", "value": "old"}]}
    session.save_storage_state(existing)
    adapter = FakeAdapter(valid_capture())

    assert await login_with_adapter(session, adapter, headless=True)
    assert adapter.calls == [(existing, True)]


@pytest.mark.asyncio
async def test_login_rejects_empty_recaptcha_without_overwriting_session(tmp_path):
    session = SessionManager(str(tmp_path))
    capture = replace(valid_capture(), recaptcha_token="")

    with pytest.raises(AuthenticationError, match="reCAPTCHA token"):
        await login_with_adapter(session, FakeAdapter(capture), headless=False)

    assert session.get_recaptcha_token() is None
    assert session.load_storage_state() is None


@pytest.mark.asyncio
async def test_login_rejects_storage_state_without_auth_cookie(tmp_path):
    session = SessionManager(str(tmp_path))
    capture = replace(
        valid_capture(),
        storage_state={"cookies": [{"name": "analytics", "value": "x"}]},
    )

    with pytest.raises(AuthenticationError, match="authenticated cookies"):
        await login_with_adapter(session, FakeAdapter(capture), headless=False)


@pytest.mark.asyncio
async def test_refresh_returns_new_token_after_one_capture(tmp_path):
    session = SessionManager(str(tmp_path))
    session.save_storage_state(valid_capture().storage_state)
    adapter = FakeAdapter(valid_capture())

    token = await _refresh_recaptcha_token(session, adapter=adapter)

    assert token == "browser-recaptcha"
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_refresh_returns_none_after_one_failed_capture(tmp_path):
    session = SessionManager(str(tmp_path))
    session.save_storage_state(valid_capture().storage_state)
    adapter = FakeAdapter(error=AuthenticationError("browser challenge"))

    assert await _refresh_recaptcha_token(session, adapter=adapter) is None
    assert len(adapter.calls) == 1
