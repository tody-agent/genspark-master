import json

import httpx
import pytest

from genspark_cli.client import GensparkClient, build_chat_payload
from genspark_cli.exceptions import RateLimitError, RecaptchaError, SessionExpiredError
from genspark_cli.session import SessionManager


SSE_RESPONSE = "\n".join(
    [
        'data: {"id":"project-2","type":"project_start"}',
        'data: {"message_id":"m","role":"assistant","project_id":"project-2","type":"message_start"}',
        'data: {"message_id":"m","field_name":"content","field_value":"Hello ","type":"message_field"}',
        'data: {"message_id":"m","field_name":"content","field_value":"world","type":"message_field"}',
        'data: {"type":"project_end"}',
        "",
    ]
)


def authenticated_session(tmp_path, token="browser-token"):
    session = SessionManager(str(tmp_path))
    session.save_storage_state(
        {"cookies": [{"name": "ai_session", "value": "browser-cookie"}]}
    )
    if token is not None:
        session.save_recaptcha_token(token)
    return session


async def no_refresh(session):
    return None


def test_chat_payload_contains_browser_token_and_conversation_state():
    payload = build_chat_payload(
        "hello",
        "claude-opus-4-6",
        "project-1",
        "browser-token",
        message_id="msg-1",
    )

    assert payload["project_id"] == "project-1"
    assert payload["messages"] == [
        {"role": "user", "id": "msg-1", "content": "hello"}
    ]
    assert payload["user_s_input"] == "hello"
    assert payload["g_recaptcha_token"] == "browser-token"
    assert payload["model_params"] == {
        "type": "chat",
        "model": "claude-opus-4-6",
    }
    assert "api_key" not in json.dumps(payload).lower()


@pytest.mark.asyncio
async def test_chat_accumulates_sse_and_saves_project_id(tmp_path):
    session = authenticated_session(tmp_path)

    def handler(request):
        assert request.url.path == "/api/agent/ask_proxy"
        assert "ai_session=browser-cookie" in request.headers["cookie"]
        return httpx.Response(200, text=SSE_RESPONSE)

    async with GensparkClient(
        session,
        http_transport=httpx.MockTransport(handler),
        refresh_callback=no_refresh,
    ) as client:
        result = await client.chat("hello")

    assert result.content == "Hello world"
    assert result.project_id == "project-2"
    assert session.last_project_id == "project-2"


@pytest.mark.asyncio
async def test_chat_requires_browser_cookies_before_http(tmp_path):
    session = SessionManager(str(tmp_path))

    async with GensparkClient(session, refresh_callback=no_refresh) as client:
        with pytest.raises(SessionExpiredError, match="session cookies"):
            await client.chat("hello")


@pytest.mark.asyncio
async def test_chat_missing_token_attempts_one_refresh_then_fails(tmp_path):
    session = authenticated_session(tmp_path, token=None)
    refresh_calls = 0

    async def refresh_once(current_session):
        nonlocal refresh_calls
        refresh_calls += 1
        return None

    async with GensparkClient(session, refresh_callback=refresh_once) as client:
        with pytest.raises(RecaptchaError):
            await client.chat("hello")

    assert refresh_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error_type"),
    [(401, SessionExpiredError), (429, RateLimitError)],
)
async def test_chat_maps_http_status_to_typed_error(tmp_path, status, error_type):
    session = authenticated_session(tmp_path)
    transport = httpx.MockTransport(lambda request: httpx.Response(status))

    async with GensparkClient(
        session,
        http_transport=transport,
        refresh_callback=no_refresh,
    ) as client:
        with pytest.raises(error_type):
            await client.chat("hello")


@pytest.mark.asyncio
async def test_recaptcha_error_refreshes_and_retries_once(tmp_path):
    session = authenticated_session(tmp_path, token="old-token")
    seen_tokens = []
    refresh_calls = 0

    def handler(request):
        seen_tokens.append(json.loads(request.content)["g_recaptcha_token"])
        if len(seen_tokens) == 1:
            return httpx.Response(403)
        return httpx.Response(200, text=SSE_RESPONSE)

    async def refresh_once(current_session):
        nonlocal refresh_calls
        refresh_calls += 1
        current_session.save_recaptcha_token("new-token")
        return "new-token"

    async with GensparkClient(
        session,
        http_transport=httpx.MockTransport(handler),
        refresh_callback=refresh_once,
    ) as client:
        result = await client.chat("hello")

    assert result.content == "Hello world"
    assert seen_tokens == ["old-token", "new-token"]
    assert refresh_calls == 1


@pytest.mark.asyncio
async def test_recaptcha_retry_never_refreshes_twice(tmp_path):
    session = authenticated_session(tmp_path)
    request_count = 0
    refresh_calls = 0

    def handler(request):
        nonlocal request_count
        request_count += 1
        return httpx.Response(403)

    async def refresh_once(current_session):
        nonlocal refresh_calls
        refresh_calls += 1
        current_session.save_recaptcha_token("new-token")
        return "new-token"

    async with GensparkClient(
        session,
        http_transport=httpx.MockTransport(handler),
        refresh_callback=refresh_once,
    ) as client:
        with pytest.raises(RecaptchaError):
            await client.chat("hello")

    assert request_count == 2
    assert refresh_calls == 1
