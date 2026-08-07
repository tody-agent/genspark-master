"""Browser-token HTTP client for Genspark chat."""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import Awaitable, Callable
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .auth import _refresh_recaptcha_token
from .exceptions import (
    APIError,
    NetworkError,
    RateLimitError,
    RecaptchaError,
    SessionExpiredError,
    TimeoutError as GensparkTimeoutError,
)
from .log import log
from .models import DEFAULT_MODEL
from .parser import ChatChunk, ChatResponse, parse_sse_stream
from .session import SessionManager


GENSPARK_API_URL = "https://www.genspark.ai/api/agent/ask_proxy"
GENSPARK_ORIGIN = "https://www.genspark.ai"
GENSPARK_REFERER = "https://www.genspark.ai/agents?type=ai_chat"
DEFAULT_HEADERS = {
    "Accept": "text/event-stream",
    "Content-Type": "application/json",
    "Origin": GENSPARK_ORIGIN,
    "Referer": GENSPARK_REFERER,
    "User-Agent": "Mozilla/5.0 GensparkMaster/0.5",
}


def build_chat_payload(
    prompt: str,
    model: str,
    project_id: str | None,
    recaptcha_token: str,
    *,
    message_id: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    identifier = message_id or str(uuid.uuid4())
    message = {"role": "user", "id": identifier, "content": prompt}
    # Allow callers (interactive REPL, MCP) to supply multi-turn history.
    # When omitted, fall back to a single-turn payload for backward compat.
    payload_messages = messages if messages else [message]
    return {
        "model_params": {"type": "chat", "model": model},
        "type": "ai_chat_agent",
        "project_id": project_id,
        "messages": payload_messages,
        "user_s_input": prompt,
        "writingContent": None,
        "use_moa_proxy": False,
        "ai_chat_enable_search": False,
        "g_recaptcha_token": recaptcha_token,
        "is_private": True,
        "push_token": "",
        "session_state": {"steps": [], "messages": payload_messages},
    }


class GensparkClient:
    def __init__(
        self,
        session: SessionManager,
        model: str = DEFAULT_MODEL,
        timeout: float = 180.0,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        refresh_callback: Callable[[SessionManager], Awaitable[str | None]] | None = None,
    ):
        self.session = session
        self.model = model
        self.timeout = timeout
        self._http_transport = http_transport
        self._refresh_callback = refresh_callback or _refresh_recaptcha_token
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.close()

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def is_closed(self) -> bool:
        """True when there is no live httpx client (or it has been closed)."""
        return self._http is None or self._http.is_closed

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._http is not None and not self._http.is_closed:
            return self._http

        cookies = self.session.get_cookies_dict()
        if not cookies:
            raise SessionExpiredError("No browser session cookies found")

        self._http = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            cookies=cookies,
            timeout=httpx.Timeout(self.timeout),
            transport=self._http_transport,
            follow_redirects=True,
        )
        return self._http

    @staticmethod
    def _check_status(response: httpx.Response) -> None:
        status = response.status_code
        if status == 200:
            return
        if status in {401, 419}:
            raise SessionExpiredError(
                "Genspark rejected the browser session cookies",
                details=f"HTTP {status}",
            )
        if status == 403:
            raise RecaptchaError(status_code=status)
        if status == 429:
            raise RateLimitError(status_code=status)
        raise APIError(
            "Unexpected response from Genspark",
            status_code=status,
        )

    async def _chat_stream_once(
        self,
        prompt: str,
        model: str,
        *,
        project_id: str | None = None,
        messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        client = await self._ensure_client()
        recaptcha_token = self.session.get_recaptcha_token()
        if not recaptcha_token:
            raise RecaptchaError("No browser reCAPTCHA token found")

        # Caller-provided project_id wins; otherwise continue the last thread.
        effective_project_id = project_id if project_id is not None else self.session.last_project_id
        payload = build_chat_payload(
            prompt,
            model,
            effective_project_id,
            recaptcha_token,
            messages=messages,
        )
        try:
            async with client.stream(
                "POST",
                GENSPARK_API_URL,
                json=payload,
            ) as response:
                self._check_status(response)
                async for line in response.aiter_lines():
                    for chunk in parse_sse_stream(line):
                        yield chunk
        except httpx.TimeoutException as exc:
            raise GensparkTimeoutError(
                timeout_seconds=self.timeout,
            ) from exc
        except httpx.RequestError as exc:
            raise NetworkError(details=str(exc)) from exc

    async def chat_stream(
        self,
        prompt: str,
        model: str | None = None,
        *,
        project_id: str | None = None,
        messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        selected_model = model or self.model
        refresh_attempted = False

        while True:
            try:
                async for chunk in self._chat_stream_once(
                    prompt,
                    selected_model,
                    project_id=project_id,
                    messages=messages,
                ):
                    if chunk.project_id:
                        self.session.last_project_id = chunk.project_id
                    yield chunk
                return
            except RecaptchaError as exc:
                if refresh_attempted:
                    raise
                refresh_attempted = True
                refreshed = await self._refresh_callback(self.session)
                if not refreshed:
                    raise exc
                await self.close()

    async def chat(
        self,
        prompt: str,
        model: str | None = None,
        *,
        project_id: str | None = None,
        messages: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        selected_model = model or self.model
        response = ChatResponse(model=selected_model)
        content_parts: list[str] = []

        async for chunk in self.chat_stream(
            prompt,
            selected_model,
            project_id=project_id,
            messages=messages,
        ):
            response.chunks.append(chunk)
            if chunk.content:
                content_parts.append(chunk.content)
            if chunk.project_id:
                response.project_id = chunk.project_id

        response.content = "".join(content_parts)
        return response


def run_chat(
    session: SessionManager,
    prompt: str,
    model: str,
    stream: bool = False,
    *,
    project_id: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> ChatResponse:
    """Run a chat request from synchronous Click commands."""

    async def runner() -> ChatResponse:
        async with GensparkClient(session, model=model) as client:
            if not stream:
                return await client.chat(
                    prompt, model=model, project_id=project_id, messages=messages
                )

            response = ChatResponse(model=model)
            content_parts: list[str] = []
            async for chunk in client.chat_stream(
                prompt, model=model, project_id=project_id, messages=messages
            ):
                response.chunks.append(chunk)
                if chunk.content:
                    content_parts.append(chunk.content)
                    sys.stdout.write(chunk.content)
                    sys.stdout.flush()
                if chunk.project_id:
                    response.project_id = chunk.project_id
            if content_parts:
                sys.stdout.write("\n")
            response.content = "".join(content_parts)
            return response

    log.debug(
        "Starting chat request",
        extra={"event": "chat_start", "model": model},
    )
    return asyncio.run(runner())
