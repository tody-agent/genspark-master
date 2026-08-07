"""Browser-token authentication for Genspark."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Protocol

from .exceptions import AuthenticationError, GensparkError
from .log import log
from .session import AUTH_COOKIES, SessionManager


GENSPARK_HOME = "https://www.genspark.ai/"
ASK_PROXY_PATH = "/api/agent/ask_proxy"
DEFAULT_LOGIN_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class CapturedBrowserSession:
    storage_state: dict[str, Any]
    recaptcha_token: str


class BrowserLoginAdapter(Protocol):
    async def capture(
        self,
        existing_state: dict[str, Any] | None,
        headless: bool,
    ) -> CapturedBrowserSession: ...


class PlaywrightBrowserAdapter:
    """Capture authenticated browser state from a real Genspark request."""

    def __init__(self, timeout_seconds: float = DEFAULT_LOGIN_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds

    async def capture(
        self,
        existing_state: dict[str, Any] | None,
        headless: bool,
    ) -> CapturedBrowserSession:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise AuthenticationError(
                "Playwright is not installed",
                suggestion=(
                    "Install browser support with: pip install -e '.[browser]' "
                    "&& python -m playwright install chromium"
                ),
            ) from exc

        captured_token: str | None = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=headless)
                try:
                    context_options: dict[str, Any] = {}
                    if existing_state:
                        context_options["storage_state"] = existing_state
                    context = await browser.new_context(**context_options)
                    page = await context.new_page()

                    def inspect_request(request) -> None:
                        nonlocal captured_token
                        if ASK_PROXY_PATH not in request.url:
                            return
                        try:
                            payload = request.post_data_json
                            if callable(payload):
                                payload = payload()
                        except Exception:
                            return
                        if not isinstance(payload, dict):
                            return
                        token = payload.get("g_recaptcha_token")
                        if isinstance(token, str) and token.strip():
                            captured_token = token.strip()

                    page.on("request", inspect_request)
                    await page.goto(GENSPARK_HOME, wait_until="domcontentloaded")

                    loop = asyncio.get_running_loop()
                    deadline = loop.time() + self.timeout_seconds
                    while captured_token is None and loop.time() < deadline:
                        if page.is_closed():
                            break
                        await asyncio.sleep(0.25)

                    if captured_token is None:
                        raise AuthenticationError(
                            "Timed out waiting for an authenticated Genspark request",
                            suggestion=(
                                "Complete login in the browser and send one chat message "
                                "before the login timeout expires."
                            ),
                        )

                    storage_state = await context.storage_state()
                finally:
                    await browser.close()
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError(
                "Unable to start or use the login browser",
                details=str(exc),
                suggestion=(
                    "Install Chromium with: python -m playwright install chromium"
                ),
            ) from exc

        return CapturedBrowserSession(
            storage_state=storage_state,
            recaptcha_token=captured_token,
        )


async def login_with_adapter(
    session: SessionManager,
    adapter: BrowserLoginAdapter,
    headless: bool,
) -> bool:
    existing_state = session.load_storage_state()
    captured = await adapter.capture(existing_state, headless)
    token = captured.recaptcha_token.strip()
    if not token:
        raise AuthenticationError("Browser did not capture a reCAPTCHA token")

    cookies = captured.storage_state.get("cookies", [])
    cookie_names = {
        item.get("name")
        for item in cookies
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if not cookie_names.intersection(AUTH_COOKIES):
        raise AuthenticationError(
            "Browser session did not contain authenticated cookies"
        )

    session.save_storage_state(captured.storage_state)
    session.save_recaptcha_token(token)
    return True


async def _refresh_recaptcha_token(
    session: SessionManager,
    *,
    adapter: BrowserLoginAdapter | None = None,
) -> str | None:
    selected_adapter = adapter or PlaywrightBrowserAdapter(
        timeout_seconds=float(os.environ.get("GENSPARK_REFRESH_TIMEOUT", "45"))
    )
    try:
        await login_with_adapter(session, selected_adapter, headless=True)
    except (GensparkError, OSError, ValueError) as exc:
        log.warning(
            "Browser-token refresh failed: %s",
            type(exc).__name__,
            extra={"event": "recaptcha_refresh_failed"},
        )
        return None
    return session.get_recaptcha_token()


def run_login(session: SessionManager) -> bool:
    headless = os.environ.get("GENSPARK_HEADLESS", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    timeout = float(
        os.environ.get(
            "GENSPARK_LOGIN_TIMEOUT",
            str(DEFAULT_LOGIN_TIMEOUT_SECONDS),
        )
    )
    return asyncio.run(
        login_with_adapter(
            session,
            PlaywrightBrowserAdapter(timeout_seconds=timeout),
            headless=headless,
        )
    )
