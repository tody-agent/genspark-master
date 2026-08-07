"""Image generation client for Genspark AI Image.

Cookie-Relay Architecture (shared with chat):
  - Uses httpx with cookies + reCAPTCHA token from browser session
  - Sends to /api/agent/ask_proxy with type "image_generation_agent"
    (the FREE endpoint used by genspark.ai/ai_image)
  - Parses SSE stream to extract task_id from image_generation_agent.results
  - Polls /api/spark/image_generation_task_detail for image_urls
  - Downloads generated images (watermark-free) to local filesystem

API Flow:
  1. POST /api/agent/ask_proxy {type: "image_generation_agent", model_params: {...}}
  2. SSE stream → extract task_id from image_generation_agent.results field
  3. GET /api/spark/image_generation_task_detail?task_id=XXX → image_urls
  4. Download from image_urls_nowatermark (preferred) or image_urls

Performance: ~10-30s per image depending on model and resolution.
"""

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx

from .exceptions import (
    APIError,
    AuthenticationError,
    NetworkError,
    ParseError,
    RateLimitError,
    RecaptchaError,
    SessionExpiredError,
    TimeoutError as GensparkTimeoutError,
)
from .image_models import (
    DEFAULT_IMAGE_MODEL,
    resolve_aspect_ratio,
    resolve_image_model,
    resolve_image_size,
    resolve_style,
)
from .image_parser import (
    ImageGenerationResult,
    extract_image_urls,
    parse_task_detail_response,
)
from .log import log
from .session import SessionManager

import json
import re


# ── Constants ────────────────────────────────────────────────────────────

GENSPARK_API_URL = "https://www.genspark.ai/api/agent/ask_proxy"
GENSPARK_TASK_URL = "https://www.genspark.ai/api/spark/image_generation_task_detail"
GENSPARK_ORIGIN = "https://www.genspark.ai"
GENSPARK_REFERER = "https://www.genspark.ai/ai_image"

IMAGE_TIMEOUT = 300.0     # 5 minutes max for image generation
CONNECT_TIMEOUT = 15.0
POLL_INTERVAL = 3.0       # Poll every 3 seconds
MAX_POLL_ATTEMPTS = 60    # 3 min max polling

DEFAULT_HEADERS = {
    "Accept": "text/event-stream",
    "Content-Type": "application/json",
    "Origin": GENSPARK_ORIGIN,
    "Referer": GENSPARK_REFERER,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}


class GensparkImageClient:
    """Async HTTP client for Genspark AI Image generation.

    Usage:
        async with GensparkImageClient(session) as client:
            result = await client.generate("a cyberpunk city at night")
            print(result.primary_url)

        # With options:
        async with GensparkImageClient(session) as client:
            result = await client.generate(
                "a portrait",
                model="flux-2-pro",
                style="Oil Painting",
                aspect_ratio="3:4",
                image_size="2K",
            )
            # Download to current directory
            paths = await client.download_images(result)
    """

    def __init__(
        self,
        session: SessionManager,
        model: str = DEFAULT_IMAGE_MODEL,
        timeout: float = IMAGE_TIMEOUT,
        auto_refresh: bool = True,
    ):
        self.session = session
        self.model = model
        self.timeout = timeout
        self.auto_refresh = auto_refresh
        self._http: Optional[httpx.AsyncClient] = None

    # ── Context Manager ──────────────────────────────────────────────────

    async def __aenter__(self) -> "GensparkImageClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Create or return the httpx client with current session cookies."""
        if self._http and not self._http.is_closed:
            return self._http

        cookies = self.session.get_cookies_dict()
        if not cookies:
            raise AuthenticationError(
                "No session cookies found",
                details="You need to log in first: genspark auth login",
            )

        recaptcha_token = self.session.get_recaptcha_token()
        if not recaptcha_token:
            raise AuthenticationError(
                "No reCAPTCHA token found",
                details="Login did not capture a reCAPTCHA token.",
                suggestion="Run: genspark auth login",
            )

        log.debug(
            "Creating image client with %d cookies",
            len(cookies),
            extra={"event": "image_client_init"},
        )

        self._http = httpx.AsyncClient(
            cookies=cookies,
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(
                self.timeout,
                connect=CONNECT_TIMEOUT,
            ),
            follow_redirects=True,
        )
        return self._http

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    # ── Auto Token Refresh ────────────────────────────────────────────────

    async def _try_refresh_token(self) -> bool:
        """Attempt one silent reCAPTCHA refresh for the current request."""
        log.info("Auto-refreshing reCAPTCHA token for image gen...",
                 extra={"event": "image_auto_refresh_start"})

        try:
            from .auth import _refresh_recaptcha_token
            token = await _refresh_recaptcha_token(self.session)
            if token:
                log.info("Token auto-refreshed for image gen",
                         extra={"event": "image_auto_refresh_done"})
                await self.close()
                return True
            return False
        except Exception as e:
            log.error("Image auto-refresh failed: %s", e, exc_info=True)
            return False

    # ── Generate ─────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        style: str = "auto",
        aspect_ratio: str = "auto",
        image_size: str = "auto",
        auto_prompt: bool = True,
    ) -> ImageGenerationResult:
        """Generate an image from a text prompt.

        Args:
            prompt: Text description of the image to generate.
            model: Image model ID (default: nano-banana-2).
            style: Art style to apply (default: auto).
            aspect_ratio: Aspect ratio (e.g., "16:9", "1:1").
            image_size: Output size (e.g., "1K", "2K", "4K").
            auto_prompt: Auto-enhance the prompt for better results.

        Returns:
            ImageGenerationResult with image URLs and metadata.

        Raises:
            AuthenticationError: Not logged in.
            RecaptchaError: Token expired.
            APIError: Generation failed.
        """
        try:
            return await self._generate_inner(
                prompt, model, style, aspect_ratio, image_size, auto_prompt
            )
        except RecaptchaError:
            if self.auto_refresh:
                refreshed = await self._try_refresh_token()
                if refreshed:
                    return await self._generate_inner(
                        prompt, model, style, aspect_ratio, image_size, auto_prompt
                    )
            raise

    async def _generate_inner(
        self,
        prompt: str,
        model: Optional[str] = None,
        style: str = "auto",
        aspect_ratio: str = "auto",
        image_size: str = "auto",
        auto_prompt: bool = True,
    ) -> ImageGenerationResult:
        """Internal generate implementation."""
        model_name = model or self.model
        model_info = resolve_image_model(model_name)
        resolved_style = resolve_style(style)
        resolved_ratio = resolve_aspect_ratio(aspect_ratio)
        resolved_size = resolve_image_size(image_size)

        client = await self._ensure_client()
        payload = self._build_payload(
            prompt=prompt,
            model_id=model_info.id,
            style=resolved_style,
            aspect_ratio=resolved_ratio,
            image_size=resolved_size,
            auto_prompt=auto_prompt,
        )

        t0 = time.monotonic()
        log.info(
            "Starting image generation",
            extra={
                "model": model_info.id,
                "style": resolved_style,
                "ratio": resolved_ratio,
                "event": "image_gen_start",
            },
        )

        raw_chunks: list[str] = []

        try:
            async with client.stream("POST", GENSPARK_API_URL, json=payload) as resp:
                self._check_status(resp)
                async for text in resp.aiter_text():
                    raw_chunks.append(text)

        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - t0
            raise GensparkTimeoutError(
                f"Image generation timed out after {elapsed:.1f}s",
                timeout_seconds=elapsed,
            ) from exc
        except httpx.ConnectError as exc:
            raise NetworkError(
                "Could not connect to Genspark",
                details=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise NetworkError(
                "HTTP error during image generation",
                details=str(exc),
            ) from exc

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_text = "".join(raw_chunks)

        if not raw_text.strip():
            raise ParseError(
                "Empty response from image generation API",
                details=f"Body is empty after {elapsed_ms}ms",
            )

        # Check for credit exhausted
        if "CREDIT_EXHAUSTED" in raw_text or "used all your credits" in raw_text:
            raise RateLimitError(
                "Image generation credit exhausted",
                status_code=429,
                body="You've used all your credits for this Genspark account.",
            )

        # Extract task_id from the SSE stream
        # The image_generation_agent returns task_id in the
        # "image_generation_agent.results" project_field
        task_id = self._extract_task_id(raw_text)
        refined_prompt = self._extract_refined_prompt(raw_text)

        result = ImageGenerationResult(
            model=model_info.display_name,
            style=resolved_style,
            task_id=task_id,
            refined_prompt=refined_prompt,
        )

        if not task_id:
            # Try to extract image URLs directly from SSE content
            result.urls = extract_image_urls(raw_text)
            if not result.has_images:
                if "project_start" in raw_text and "content" not in raw_text:
                    raise RecaptchaError(
                        "reCAPTCHA token may be expired — got no image content",
                    )
                raise ParseError(
                    "No task_id or image URLs found in response",
                    details=f"Response had {len(raw_text)} bytes after {elapsed_ms}ms",
                )
        else:
            # Poll the task until we get image URLs
            log.info(
                "Polling task %s for image results...",
                task_id,
                extra={"event": "image_poll_start"},
            )
            polled = await self._poll_task(task_id)
            result.urls = polled.urls
            result.width = polled.width
            result.height = polled.height
            if polled.refined_prompt and not result.refined_prompt:
                result.refined_prompt = polled.refined_prompt

        if not result.has_images:
            raise ParseError(
                "No images found after polling",
                details=f"task_id={task_id}, response had {len(raw_text)} bytes",
            )

        log.info(
            "Image generated: %d images in %dms",
            len(result.urls),
            elapsed_ms,
            extra={
                "model": model_info.id,
                "image_count": len(result.urls),
                "duration_ms": elapsed_ms,
                "event": "image_gen_done",
            },
        )

        return result

    def _extract_task_id(self, raw_text: str) -> Optional[str]:
        """Extract task_id from the SSE stream.

        The image_generation_agent returns task_id in:
          field_name: "image_generation_agent.results"
          field_value: [{"task_id": "xxx", ...}]
        """
        # Pattern 1: image_generation_agent.results field
        for line in raw_text.split("\n"):
            line = line.strip()
            if not line.startswith("data: "):
                continue
            try:
                data = json.loads(line[6:])
                field_name = data.get("field_name", "")
                if "image_generation_agent.results" in field_name:
                    field_value = data.get("field_value", [])
                    if isinstance(field_value, list) and field_value:
                        return field_value[0].get("task_id")
            except (json.JSONDecodeError, TypeError, IndexError, KeyError):
                continue

        # Pattern 2: task_id in tool content
        task_id_match = re.search(r'"task_id":\s*"([^"]+)"', raw_text)
        if task_id_match:
            return task_id_match.group(1)

        return None

    def _extract_refined_prompt(self, raw_text: str) -> Optional[str]:
        """Extract the AI-enhanced prompt from the SSE stream."""
        for line in raw_text.split("\n"):
            line = line.strip()
            if not line.startswith("data: "):
                continue
            try:
                data = json.loads(line[6:])
                field_name = data.get("field_name", "")
                if "image_generation_agent.results" in field_name:
                    field_value = data.get("field_value", [])
                    if isinstance(field_value, list) and field_value:
                        return field_value[0].get("prompt")
            except (json.JSONDecodeError, TypeError, IndexError, KeyError):
                continue
        return None

    # ── Poll Task ────────────────────────────────────────────────────────

    async def _poll_task(self, task_id: str) -> ImageGenerationResult:
        """Poll an async image generation task until completion.

        Args:
            task_id: The task ID from the initial generation request.

        Returns:
            ImageGenerationResult from the completed task.
        """
        client = await self._ensure_client()

        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                resp = await client.get(
                    GENSPARK_TASK_URL,
                    params={"task_id": task_id},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result = parse_task_detail_response(data)

                    if result.has_images:
                        return result

                    # Check for failure states
                    status = data.get("data", {}).get("status", "")
                    if status in ("failed", "error", "cancelled"):
                        raise APIError(
                            f"Image generation task {status}",
                            details=str(data),
                        )

            except httpx.HTTPError as exc:
                log.warning("Poll attempt %d failed: %s", attempt + 1, exc)

            await asyncio.sleep(POLL_INTERVAL)

        raise GensparkTimeoutError(
            f"Image generation task {task_id} did not complete within {MAX_POLL_ATTEMPTS * POLL_INTERVAL}s",
        )

    # ── Download ─────────────────────────────────────────────────────────

    async def download_images(
        self,
        result: ImageGenerationResult,
        output_dir: Optional[str] = None,
        filename_prefix: str = "genspark",
    ) -> list[str]:
        """Download generated images to local filesystem.

        Args:
            result: ImageGenerationResult with URLs.
            output_dir: Directory to save images (default: CWD).
            filename_prefix: Prefix for filenames.

        Returns:
            List of local file paths where images were saved.
        """
        if not result.has_images:
            return []

        output_path = Path(output_dir) if output_dir else Path.cwd()
        output_path.mkdir(parents=True, exist_ok=True)

        client = await self._ensure_client()
        paths: list[str] = []

        for i, url in enumerate(result.urls):
            try:
                # Determine file extension from URL
                ext = _guess_extension(url)
                timestamp = int(time.time())
                filename = f"{filename_prefix}_{timestamp}_{i + 1}{ext}"
                filepath = output_path / filename

                # Download the image
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200:
                    filepath.write_bytes(resp.content)
                    paths.append(str(filepath))
                    log.info(
                        "Image saved: %s (%d bytes)",
                        filepath,
                        len(resp.content),
                        extra={"event": "image_download", "path": str(filepath)},
                    )
                else:
                    log.warning(
                        "Failed to download image %s (HTTP %d)",
                        url, resp.status_code,
                    )
            except Exception as e:
                log.error("Error downloading image: %s", e, exc_info=True)

        result.local_paths = paths
        return paths

    # ── Private Helpers ──────────────────────────────────────────────────

    def _build_payload(
        self,
        prompt: str,
        model_id: str,
        style: str = "auto",
        aspect_ratio: str = "auto",
        image_size: str = "auto",
        auto_prompt: bool = True,
    ) -> dict:
        """Build the JSON payload for image generation.

        Uses model_params format that differs from the chat API's flat format.
        """
        msg_id = str(uuid.uuid4())
        recaptcha_token = self.session.get_recaptcha_token() or ""

        current_msg = {
            "role": "user",
            "id": msg_id,
            "content": prompt,
        }

        messages = [current_msg]

        return {
            "model_params": {
                "type": "image",
                "model": model_id,
                "aspect_ratio": aspect_ratio,
                "auto_prompt": auto_prompt,
                "style": style,
                "image_size": image_size,
                "background_mode": True,
                "camera_control": {
                    "yaw": 0,
                    "tilt": 0,
                    "zoom": 0,
                    "wide_angle_lens": False,
                },
            },
            "type": "image_generation_agent",
            "project_id": None,
            "messages": messages,
            "user_s_input": prompt,
            "writingContent": None,
            "use_moa_proxy": False,
            "ai_chat_enable_search": False,
            "g_recaptcha_token": recaptcha_token,
            "is_private": True,
            "push_token": "",
            "session_state": {
                "steps": [],
                "messages": messages,
            },
        }

    def _check_status(self, response: httpx.Response) -> None:
        """Inspect HTTP status and raise structured exceptions."""
        status = response.status_code

        if status == 200:
            return

        body_preview = ""
        try:
            body_preview = str(dict(response.headers))[:500]
        except Exception:
            pass

        log.error(
            "Image API returned HTTP %d",
            status,
            extra={"status_code": status, "event": "image_api_error"},
        )

        if status in (401, 403):
            raise SessionExpiredError(
                details=f"HTTP {status}. Cookies may have expired.",
            )
        elif status == 429:
            raise RateLimitError(
                status_code=status,
                body=body_preview,
            )
        elif status == 418 or "captcha" in body_preview.lower():
            raise RecaptchaError(
                status_code=status,
                body=body_preview,
            )
        else:
            raise APIError(
                "Image generation API error",
                status_code=status,
                body=body_preview,
            )


def _guess_extension(url: str) -> str:
    """Guess image file extension from URL."""
    url_lower = url.lower().split("?")[0]
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
        if url_lower.endswith(ext):
            return ext
    return ".png"  # default


# ── Synchronous Convenience ──────────────────────────────────────────────

def run_image_generate(
    session: SessionManager,
    prompt: str,
    model: str = DEFAULT_IMAGE_MODEL,
    style: str = "auto",
    aspect_ratio: str = "auto",
    image_size: str = "auto",
    auto_prompt: bool = True,
    output_dir: Optional[str] = None,
    download: bool = True,
) -> ImageGenerationResult:
    """Synchronous wrapper — generate an image and optionally download it.

    Used by cli.py for the `genspark image generate` command.

    Args:
        session: SessionManager with cookies and tokens.
        prompt: Text description of the image.
        model: Image model ID.
        style: Art style to apply.
        aspect_ratio: Aspect ratio string.
        image_size: Output size string.
        auto_prompt: Auto-enhance prompt.
        output_dir: Where to save images (default: CWD).
        download: Whether to download images.

    Returns:
        ImageGenerationResult with URLs and local paths.
    """

    async def _run() -> ImageGenerationResult:
        async with GensparkImageClient(session, model=model) as client:
            result = await client.generate(
                prompt=prompt,
                style=style,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                auto_prompt=auto_prompt,
            )
            if download and result.has_images:
                await client.download_images(
                    result,
                    output_dir=output_dir,
                )
            return result

    return asyncio.run(_run())
