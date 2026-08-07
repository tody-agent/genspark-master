"""OpenAI-compatible API proxy server.

Translates OpenAI API format to Genspark httpx calls,
allowing any OpenAI-compatible client to use Genspark's free AI models.

v2: Uses pure httpx client (no browser per request).

Endpoints:
    GET  /v1/models              — List available models
    POST /v1/chat/completions    — Chat completion (streaming & non-streaming)
    GET  /health                 — Health check
"""

import asyncio
import json
import time
import uuid
from typing import Optional

from aiohttp import web

from . import __version__
from .client import GensparkClient
from .exceptions import GensparkError
from .log import log
from .models import (
    DEFAULT_MODEL,
    MODELS,
    OPENAI_TO_GENSPARK,
    list_models,
    resolve_model,
)
from .parser import format_sse_chunk_openai, ChatChunk
from .session import SessionManager


# ── Client Pool ──────────────────────────────────────────────────────────

class ClientPool:
    """Manages GensparkClient instances with multi-account failover.

    Uses AccountRouter to select the best available account.
    On failure, marks the account unhealthy and retries with the next one.
    """

    def __init__(self, default_model: str = DEFAULT_MODEL):
        from .profiles import ProfileManager
        from .account_router import AccountRouter

        self.pm = ProfileManager()
        self.router = AccountRouter(self.pm)
        self.default_model = default_model
        self._clients: dict[str, GensparkClient] = {}
        self._lock = asyncio.Lock()

    async def get_client(self, preferred_profile: Optional[str] = None) -> GensparkClient:
        """Get or create a GensparkClient for the best available account."""
        async with self._lock:
            try:
                session = self.router.get_session(preferred=preferred_profile)
            except RuntimeError as e:
                log.error("No accounts available: %s", e)
                raise

            profile_name = session.profile_name

            if profile_name in self._clients:
                client = self._clients[profile_name]
                if not client.is_closed:
                    return client

            client = GensparkClient(
                session=session,
                model=self.default_model,
            )
            await client._ensure_client()
            self._clients[profile_name] = client
            log.info(
                "Server client initialized for profile '%s'",
                profile_name,
                extra={"event": "pool_init", "profile": profile_name},
            )
            return client

    def mark_unhealthy(self, profile_name: str, reason: str = "api_error") -> None:
        """Mark a profile as unhealthy after a failure."""
        self.router.mark_unhealthy(profile_name, reason=reason)
        # Close the failed client
        if profile_name in self._clients:
            client = self._clients.pop(profile_name)
            asyncio.create_task(client.close())

    def mark_success(self, profile_name: str) -> None:
        """Mark a profile as healthy after a successful request."""
        self.router.mark_success(profile_name)

    @property
    def session(self) -> SessionManager:
        """Backward compatible — return default session."""
        return self.pm.get_session()

    async def close(self):
        for name, client in self._clients.items():
            await client.close()
        self._clients.clear()
        log.info("Server client pool closed", extra={"event": "pool_close"})


# ── Request Handlers ─────────────────────────────────────────────────────

async def handle_models(request: web.Request) -> web.Response:
    """GET /v1/models — List available models in OpenAI format."""
    models = list_models()
    data = {
        "object": "list",
        "data": [
            {
                "id": m.id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": m.provider,
                "permission": [],
                "root": m.id,
                "parent": None,
            }
            for m in models
        ],
    }
    return web.json_response(data)


async def handle_chat_completions(request: web.Request) -> web.Response:
    """POST /v1/chat/completions — Chat completion in OpenAI format."""
    pool: ClientPool = request.app["client_pool"]

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": {"message": "Invalid JSON", "type": "invalid_request_error"}},
            status=400,
        )

    # Extract parameters
    messages = body.get("messages", [])
    model_name = body.get("model", pool.default_model)
    stream = body.get("stream", False)

    if not messages:
        return web.json_response(
            {"error": {"message": "messages is required", "type": "invalid_request_error"}},
            status=400,
        )

    # Resolve model
    try:
        if model_name in OPENAI_TO_GENSPARK:
            genspark_model = OPENAI_TO_GENSPARK[model_name]
        else:
            model_info = resolve_model(model_name)
            genspark_model = model_info.id
    except ValueError:
        genspark_model = pool.default_model

    # Build prompt from messages
    prompt = _messages_to_prompt(messages)

    # Get client
    client = await pool.get_client()

    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    log.debug(
        "Proxy request: model=%s stream=%s prompt_len=%d",
        genspark_model, stream, len(prompt),
        extra={"model": genspark_model, "event": "proxy_request"},
    )

    if stream:
        return await _handle_stream(request, pool, client, prompt, genspark_model, request_id)
    else:
        return await _handle_non_stream(pool, client, prompt, genspark_model, request_id)


async def _handle_non_stream(
    pool: ClientPool,
    client: GensparkClient,
    prompt: str,
    model: str,
    request_id: str,
) -> web.Response:
    """Handle non-streaming chat completion."""
    from .exceptions import RateLimitError, SessionExpiredError, RecaptchaError
    try:
        result = await client.chat(prompt, model=model)
        pool.mark_success(client.session.profile_name)

        response = {
            "id": request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result.content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(result.content.split()),
                "total_tokens": len(prompt.split()) + len(result.content.split()),
            },
        }
        return web.json_response(response)

    except (RateLimitError, SessionExpiredError, RecaptchaError) as e:
        log.warning("Proxy failover triggered: %s", e, extra={"event": "proxy_failover"})
        pool.mark_unhealthy(client.session.profile_name, reason=type(e).__name__)
        # Auto-retry with next account
        try:
            client = await pool.get_client()
            result = await client.chat(prompt, model=model)
            pool.mark_success(client.session.profile_name)

            response = {
                "id": request_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": result.content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(result.content.split()),
                    "total_tokens": len(prompt.split()) + len(result.content.split()),
                },
            }
            return web.json_response(response)
        except Exception as retry_err:
            return web.json_response(
                {"error": {"message": f"All accounts failed: {retry_err}", "type": "server_error"}},
                status=503,
            )
    except GensparkError as e:
        log.error("Proxy error: %s", e, extra={"event": "proxy_error"})
        return web.json_response(
            {"error": {"message": str(e), "type": "server_error"}},
            status=500,
        )
    except Exception as e:
        log.error("Proxy unexpected error: %s", e, exc_info=True, extra={"event": "proxy_error"})
        return web.json_response(
            {"error": {"message": str(e), "type": "server_error"}},
            status=500,
        )


async def _handle_stream(
    request: web.Request,
    pool: ClientPool,
    client: GensparkClient,
    prompt: str,
    model: str,
    request_id: str,
) -> web.StreamResponse:
    """Handle streaming chat completion."""
    from .exceptions import RateLimitError, SessionExpiredError, RecaptchaError
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await response.prepare(request)

    try:
        # Send initial role chunk
        initial = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        await response.write(f"data: {json.dumps(initial)}\n\n".encode())

        async for chunk in client.chat_stream(prompt, model=model):
            sse_line = format_sse_chunk_openai(chunk, model=model, chunk_id=request_id)
            await response.write(sse_line.encode())

        # Send done signal
        await response.write(b"data: [DONE]\n\n")
        pool.mark_success(client.session.profile_name)

    except (RateLimitError, SessionExpiredError, RecaptchaError) as e:
        log.warning("Stream proxy failover triggered: %s", e, extra={"event": "stream_failover"})
        pool.mark_unhealthy(client.session.profile_name, reason=type(e).__name__)
        error_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {"content": f"\n\n[Error: Connection lost. Auto-failing over to next account. Please try again.]"}, "finish_reason": "stop"}],
        }
        await response.write(f"data: {json.dumps(error_chunk)}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")
    except GensparkError as e:
        log.error("Stream proxy error: %s", e, extra={"event": "stream_error"})
        error_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {"content": f"\n\n[Error: {e}]"}, "finish_reason": "stop"}],
        }
        await response.write(f"data: {json.dumps(error_chunk)}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")
    except Exception as e:
        log.error("Stream unexpected error: %s", e, exc_info=True, extra={"event": "stream_error"})
        error_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {"content": f"\n\n[Error: {e}]"}, "finish_reason": "stop"}],
        }
        await response.write(f"data: {json.dumps(error_chunk)}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")

    return response


async def handle_image_generations(request: web.Request) -> web.Response:
    """POST /v1/images/generations — OpenAI Images API compatible.

    Request format:
        {"model": "flux-2", "prompt": "a cat", "n": 1, "size": "1024x1024"}

    Response format:
        {"created": 1234, "data": [{"url": "https://..."}]}
    """
    from .image_client import GensparkImageClient
    from .image_models import DEFAULT_IMAGE_MODEL, resolve_image_model

    pool: ClientPool = request.app["client_pool"]

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": {"message": "Invalid JSON", "type": "invalid_request_error"}},
            status=400,
        )

    prompt = body.get("prompt", "")
    if not prompt:
        return web.json_response(
            {"error": {"message": "prompt is required", "type": "invalid_request_error"}},
            status=400,
        )

    model_name = body.get("model", DEFAULT_IMAGE_MODEL)
    size_str = body.get("size", "auto")
    style = body.get("style", "auto")
    quality = body.get("quality", "auto")

    # Resolve model
    try:
        model_info = resolve_image_model(model_name)
    except ValueError:
        model_info = resolve_image_model(DEFAULT_IMAGE_MODEL)

    # Map OpenAI size format (e.g., "1024x1024") to Genspark params
    aspect_ratio, image_size = _openai_size_to_genspark(size_str)

    # Map quality to image_size if not already set
    if image_size == "auto" and quality in ("hd", "high"):
        image_size = "4K"

    log.info(
        "Image proxy request: model=%s prompt_len=%d",
        model_info.id, len(prompt),
        extra={"model": model_info.id, "event": "image_proxy_request"},
    )

    # Get session from pool
    try:
        client = await pool.get_client()
        session = client.session
    except RuntimeError as e:
        return web.json_response(
            {"error": {"message": str(e), "type": "server_error"}},
            status=503,
        )

    from .exceptions import RateLimitError, SessionExpiredError, RecaptchaError
    try:
        async with GensparkImageClient(session, model=model_info.id) as img_client:
            result = await img_client.generate(
                prompt=prompt,
                style=style,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )

        pool.mark_success(session.profile_name)

        response = {
            "created": int(time.time()),
            "data": [{"url": url} for url in result.urls],
        }
        return web.json_response(response)

    except (RateLimitError, SessionExpiredError, RecaptchaError) as e:
        log.warning("Image proxy failover: %s", e, extra={"event": "image_proxy_failover"})
        pool.mark_unhealthy(session.profile_name, reason=type(e).__name__)
        return web.json_response(
            {"error": {"message": f"Account failover triggered ({type(e).__name__}). Retry.", "type": "server_error"}},
            status=503,
        )
    except Exception as e:
        log.error("Image proxy error: %s", e, exc_info=True)
        return web.json_response(
            {"error": {"message": str(e), "type": "server_error"}},
            status=500,
        )


async def handle_health(request: web.Request) -> web.Response:
    """GET /health — Health check."""
    from .image_models import IMAGE_MODELS
    pool: ClientPool = request.app["client_pool"]
    return web.json_response({
        "status": "ok",
        "version": __version__,
        "backend": "httpx (multi-account)",
        "chat_models": len(MODELS),
        "image_models": len(IMAGE_MODELS),
        "accounts_total": pool.router.pool_size,
        "accounts_available": pool.router.available_count,
        "accounts": [
            {
                "name": s["name"],
                "health": s["health"],
                "available": s["is_available"]
            }
            for s in pool.router.get_status()
        ]
    })


# ── Helpers ──────────────────────────────────────────────────────────────

def _messages_to_prompt(messages: list[dict]) -> str:
    """Convert OpenAI-style messages array to a single prompt string.

    Genspark's chat is single-turn per submission, so we concatenate
    the conversation history into a formatted prompt.
    """
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            # Handle multimodal content (text parts)
            text_parts = [
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            content = "\n".join(text_parts)

        if role in ("system", "developer"):
            parts.append(f"[System Instructions]: {content}")
        elif role == "assistant":
            parts.append(f"[Previous Assistant Response]: {content}")
        elif role == "user":
            parts.append(content)

    return "\n\n".join(parts)


def _openai_size_to_genspark(size: str) -> tuple[str, str]:
    """Map OpenAI image size strings to Genspark aspect_ratio + image_size.

    OpenAI format: "1024x1024", "1792x1024", "1024x1792"
    Also accepts Genspark native: "16:9", "1:1", "auto"

    Returns:
        (aspect_ratio, image_size) tuple.
    """
    if not size or size == "auto":
        return ("auto", "auto")

    # If it's already a ratio format, pass through
    if ":" in size:
        return (size, "auto")

    # Map OpenAI WxH to (ratio, size)
    size_map = {
        "256x256": ("1:1", "0.5K"),
        "512x512": ("1:1", "0.5K"),
        "1024x1024": ("1:1", "1K"),
        "1024x1536": ("2:3", "1K"),
        "1536x1024": ("3:2", "1K"),
        "1024x1792": ("9:16", "1K"),
        "1792x1024": ("16:9", "2K"),
        "2048x2048": ("1:1", "2K"),
        "4096x4096": ("1:1", "4K"),
    }

    if size in size_map:
        return size_map[size]

    # Try to parse WxH format
    if "x" in size:
        try:
            w, h = size.split("x")
            w, h = int(w), int(h)
            # Determine closest aspect ratio
            ratio = w / h
            if abs(ratio - 1.0) < 0.1:
                ar = "1:1"
            elif ratio > 1.5:
                ar = "16:9"
            elif ratio > 1.2:
                ar = "3:2"
            elif ratio < 0.67:
                ar = "9:16"
            elif ratio < 0.8:
                ar = "2:3"
            else:
                ar = "4:3" if ratio > 1 else "3:4"
            # Determine size
            max_dim = max(w, h)
            if max_dim <= 512:
                img_size = "0.5K"
            elif max_dim <= 1024:
                img_size = "1K"
            elif max_dim <= 2048:
                img_size = "2K"
            else:
                img_size = "4K"
            return (ar, img_size)
        except (ValueError, ZeroDivisionError):
            pass

    return ("auto", "auto")


# ── CORS Middleware ──────────────────────────────────────────────────────

@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Add CORS headers for browser-based clients."""
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# ── Auth Middleware ──────────────────────────────────────────────────────

@web.middleware
async def auth_middleware(request: web.Request, handler):
    """Accept any API key (or none) — auth is handled by session cookies."""
    return await handler(request)


# ── Server Setup ─────────────────────────────────────────────────────────

def create_app(default_model: str = DEFAULT_MODEL) -> web.Application:
    """Create the aiohttp web application."""
    app = web.Application(middlewares=[cors_middleware, auth_middleware])

    # Routes
    app.router.add_get("/v1/models", handle_models)
    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_post("/v1/images/generations", handle_image_generations)
    app.router.add_get("/health", handle_health)

    # Client pool (httpx, not browser)
    pool = ClientPool(default_model=default_model)
    app["client_pool"] = pool

    async def cleanup(app):
        await pool.close()

    app.on_cleanup.append(cleanup)

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    default_model: str = DEFAULT_MODEL,
) -> None:
    """Start the OpenAI-compatible proxy server."""
    app = create_app(default_model=default_model)
    log.info("Starting server on %s:%d", host, port, extra={"event": "server_start"})
    web.run_app(app, host=host, port=port, print=lambda msg: None)
