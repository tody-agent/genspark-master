"""MCP services backed by Genspark browser sessions.

The service functions are intentionally independent from FastMCP so the core
package remains importable without the optional ``mcp`` dependency.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any

from .account_router import AccountRouter
from .client import GensparkClient
from .exceptions import RateLimitError, RecaptchaError, SessionExpiredError
from .image_client import GensparkImageClient
from .image_models import list_image_models as _list_image_models
from .models import list_models
from .profiles import ProfileManager


ROUTING_ERRORS = (RateLimitError, SessionExpiredError, RecaptchaError)


def _default_router() -> AccountRouter:
    return AccountRouter(ProfileManager())


async def _with_failover(
    operation: Callable[[Any], Awaitable[dict[str, Any]]],
    router: AccountRouter,
    preferred: str | None = None,
) -> dict[str, Any]:
    """Run an operation with bounded browser-profile failover."""
    statuses = router.get_status()
    max_attempts = max(1, len(statuses))
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        session = router.get_session(preferred if attempt == 0 else None)
        profile = getattr(session, "profile_name", "default")
        try:
            result = await operation(session)
            router.mark_success(profile)
            result.setdefault("profile", profile)
            return result
        except ROUTING_ERRORS as exc:
            last_error = exc
            router.mark_unhealthy(profile, reason=type(exc).__name__)

    if last_error is not None:
        raise last_error
    raise RuntimeError("No Genspark browser profiles are available")


async def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if close is not None:
        await close()


async def chat(
    prompt: str,
    model: str | None = None,
    project_id: str | None = None,
    profile: str | None = None,
    *,
    router: AccountRouter | None = None,
    client_factory: Callable[[Any], Any] = GensparkClient,
) -> dict[str, Any]:
    """Send a chat message using a saved browser-token profile."""
    account_router = router or _default_router()

    async def operation(session: Any) -> dict[str, Any]:
        client = client_factory(session)
        try:
            response = await client.chat(prompt, model=model, project_id=project_id)
            return {
                "content": response.content,
                "role": response.role,
                "model": response.model,
                "project_id": response.project_id,
            }
        finally:
            await _close_client(client)

    return await _with_failover(operation, account_router, profile)


async def chat_with_context(
    prompt: str,
    context: str | dict[str, Any] | list[Any],
    model: str | None = None,
    project_id: str | None = None,
    profile: str | None = None,
    *,
    router: AccountRouter | None = None,
    client_factory: Callable[[Any], Any] = GensparkClient,
) -> dict[str, Any]:
    """Send a message with explicit caller-supplied context."""
    context_text = context if isinstance(context, str) else json.dumps(context, ensure_ascii=False)
    contextual_prompt = f"Context:\n{context_text}\n\nRequest:\n{prompt}"
    return await chat(
        contextual_prompt,
        model=model,
        project_id=project_id,
        profile=profile,
        router=router,
        client_factory=client_factory,
    )


def get_models() -> dict[str, Any]:
    """Return the locally known Genspark chat model registry."""
    return {"models": [asdict(model) for model in list_models()]}


def check_status(*, router: AccountRouter | None = None) -> dict[str, Any]:
    """Return local browser-profile routing health without a network call."""
    account_router = router or _default_router()
    return {"profiles": account_router.get_status()}


async def generate_image(
    prompt: str,
    model: str | None = None,
    style: str = "auto",
    aspect_ratio: str = "auto",
    image_size: str = "auto",
    profile: str | None = None,
    *,
    router: AccountRouter | None = None,
    client_factory: Callable[[Any], Any] = GensparkImageClient,
) -> dict[str, Any]:
    """Generate an image using a saved browser-token profile."""
    account_router = router or _default_router()

    async def operation(session: Any) -> dict[str, Any]:
        client = client_factory(session)
        try:
            result = await client.generate(
                prompt,
                model=model,
                style=style,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
            return asdict(result)
        finally:
            await _close_client(client)

    return await _with_failover(operation, account_router, profile)


def list_image_models() -> dict[str, Any]:
    """Return the locally known Genspark image model registry."""
    return {"models": [asdict(model) for model in _list_image_models()]}


def create_mcp_server() -> Any:
    """Create and register the six MCP tools lazily across MCP 1.x/2.x."""
    try:
        from mcp.server.fastmcp import FastMCP
    except (ImportError, ModuleNotFoundError):
        try:
            from mcp.server import MCPServer as FastMCP
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "Install MCP support with: pip install -e '.[mcp]'"
            ) from exc

    server = FastMCP(
        "genspark-master",
        instructions=(
            "Use Genspark chat and image generation through locally saved "
            "browser sessions. This server does not use API keys."
        ),
    )

    async def chat_tool(
        prompt: str,
        model: str | None = None,
        project_id: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        return await chat(prompt, model, project_id, profile)

    async def chat_with_context_tool(
        prompt: str,
        context: str,
        model: str | None = None,
        project_id: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        return await chat_with_context(prompt, context, model, project_id, profile)

    def get_models_tool() -> dict[str, Any]:
        return get_models()

    def check_status_tool() -> dict[str, Any]:
        return check_status()

    async def generate_image_tool(
        prompt: str,
        model: str | None = None,
        style: str = "auto",
        aspect_ratio: str = "auto",
        image_size: str = "auto",
        profile: str | None = None,
    ) -> dict[str, Any]:
        return await generate_image(
            prompt,
            model,
            style,
            aspect_ratio,
            image_size,
            profile,
        )

    def list_image_models_tool() -> dict[str, Any]:
        return list_image_models()

    server.tool(name="chat")(chat_tool)
    server.tool(name="chat_with_context")(chat_with_context_tool)
    server.tool(name="get_models")(get_models_tool)
    server.tool(name="check_status")(check_status_tool)
    server.tool(name="generate_image")(generate_image_tool)
    server.tool(name="list_image_models")(list_image_models_tool)
    return server


def run_mcp_server() -> None:
    """Start the stdio MCP server."""
    if any(argument in {"-h", "--help"} for argument in sys.argv[1:]):
        print("Usage: genspark-mcp\n\nRun the Genspark MCP server over stdio.")
        return
    create_mcp_server().run()


if __name__ == "__main__":
    run_mcp_server()
