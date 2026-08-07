"""Image-specific SSE parser for Genspark AI Image.

Parses the server-sent events stream from the image generation API,
extracting task IDs, image URLs, dimensions, and refined prompts.

The image generation SSE stream differs from chat:
  - Contains `tool_calls` events with image generation parameters
  - Returns image URLs in content fields or tool result events
  - May include task_id for async polling
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ImageGenerationResult:
    """Result of an image generation request."""

    urls: list[str] = field(default_factory=list)
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    refined_prompt: Optional[str] = None
    model: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    style: Optional[str] = None
    local_paths: list[str] = field(default_factory=list)
    raw_content: str = ""
    credit_exhausted: bool = False

    @property
    def has_images(self) -> bool:
        return len(self.urls) > 0

    @property
    def primary_url(self) -> Optional[str]:
        return self.urls[0] if self.urls else None


@dataclass
class ImageChunk:
    """A single chunk from the image generation SSE stream."""

    event_type: str = ""
    content: str = ""
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    image_urls: list[str] = field(default_factory=list)
    is_done: bool = False
    raw: Optional[dict] = None


def parse_image_sse_line(line: str) -> Optional[dict]:
    """Parse a single SSE line into a data dict.

    Handles both 'data: {...}' format and raw JSON lines.
    Returns None for empty lines, comments, and non-data lines.
    """
    line = line.strip()

    if not line or line.startswith(":"):
        return None

    if line.startswith("data: "):
        json_str = line[6:]
    elif line.startswith("{"):
        json_str = line
    else:
        return None

    if json_str == "[DONE]":
        return {"type": "done"}

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def extract_image_urls(text: str) -> list[str]:
    """Extract image URLs from text content (markdown or plain URLs).

    Handles:
      - Markdown images: ![alt](url)
      - Plain URLs: https://....(png|jpg|webp|...)
      - Genspark CDN URLs
    """
    urls = []

    # Markdown image pattern: ![...](url)
    md_pattern = r'!\[[^\]]*\]\(([^)]+)\)'
    for match in re.finditer(md_pattern, text):
        url = match.group(1)
        if url and url.startswith("http"):
            urls.append(url)

    # Direct URL pattern (image extensions or CDN patterns)
    url_pattern = r'https?://[^\s<>"\']+(?:\.(?:png|jpg|jpeg|webp|gif|svg)|/image[^\s<>"\']*)'
    for match in re.finditer(url_pattern, text):
        url = match.group(0)
        # Avoid duplicates from markdown extraction
        if url not in urls:
            urls.append(url)

    return urls


def parse_image_sse_to_result(raw_text: str, model: str = "") -> ImageGenerationResult:
    """Parse the complete SSE stream text into an ImageGenerationResult.

    Args:
        raw_text: The raw SSE stream text from the API.
        model: The model name for metadata.

    Returns:
        ImageGenerationResult with extracted URLs and metadata.
    """
    result = ImageGenerationResult(model=model)
    content_parts: list[str] = []

    for line in raw_text.split("\n"):
        data = parse_image_sse_line(line)
        if data is None:
            continue

        event_type = data.get("type", "")

        # Project start — capture project_id
        if event_type == "project_start":
            result.project_id = data.get("id") or data.get("project_id")

        # Message field — capture content and look for image URLs
        elif event_type == "message_field":
            field_name = data.get("field_name", "")
            field_value = data.get("field_value", "")

            if field_name == "content" and field_value:
                content_parts.append(field_value)
                # Extract image URLs from content
                urls = extract_image_urls(field_value)
                for url in urls:
                    if url not in result.urls:
                        result.urls.append(url)

            elif field_name == "tool_calls" and field_value:
                # Tool calls may contain image generation parameters/results
                _parse_tool_calls(field_value, result)

        # Message start — may contain task info
        elif event_type == "message_start":
            if data.get("project_id"):
                result.project_id = data["project_id"]
                
        # Message result — check for out of credits
        elif event_type == "message_result":
            content = data.get("message", {}).get("content", "")
            if "used all your credits" in content or "CREDIT_EXHAUSTED" in str(data):
                result.credit_exhausted = True

        # Project end
        elif event_type in ("project_end", "done"):
            pass

    result.raw_content = "".join(content_parts)

    # Final pass: extract any image URLs from assembled content
    if not result.urls and result.raw_content:
        result.urls = extract_image_urls(result.raw_content)

    return result


def _parse_tool_calls(tool_calls_str: str, result: ImageGenerationResult) -> None:
    """Parse tool_calls field value for image generation data.

    Tool calls can be a JSON string containing image generation
    parameters, task IDs, or result URLs.
    """
    try:
        if isinstance(tool_calls_str, str):
            data = json.loads(tool_calls_str)
        else:
            data = tool_calls_str
    except (json.JSONDecodeError, TypeError):
        return

    if isinstance(data, list):
        for call in data:
            _extract_from_tool_call(call, result)
    elif isinstance(data, dict):
        _extract_from_tool_call(data, result)


def _extract_from_tool_call(call: dict, result: ImageGenerationResult) -> None:
    """Extract image data from a single tool call dict."""
    # Look for task_id
    if "task_id" in call:
        result.task_id = call["task_id"]

    # Look for image URLs in various locations
    for key in ("url", "image_url", "output_url", "result_url"):
        if key in call and call[key]:
            url = call[key]
            if url not in result.urls:
                result.urls.append(url)

    # Look for URLs in nested results
    if "result" in call and isinstance(call["result"], dict):
        _extract_from_tool_call(call["result"], result)

    if "images" in call and isinstance(call["images"], list):
        for img in call["images"]:
            if isinstance(img, str) and img.startswith("http"):
                if img not in result.urls:
                    result.urls.append(img)
            elif isinstance(img, dict):
                for key in ("url", "image_url", "src"):
                    if key in img and img[key] not in result.urls:
                        result.urls.append(img[key])

    # Look for function arguments
    if "function" in call and isinstance(call["function"], dict):
        args = call["function"].get("arguments")
        if isinstance(args, str):
            try:
                args_data = json.loads(args)
                if isinstance(args_data, dict):
                    # May contain prompt or other params
                    if "prompt" in args_data:
                        result.refined_prompt = args_data["prompt"]
                    if "task_id" in args_data:
                        result.task_id = args_data["task_id"]
            except json.JSONDecodeError:
                pass


def parse_task_detail_response(data: dict) -> ImageGenerationResult:
    """Parse a task detail API response.

    Called when polling /api/spark/image_generation_task_detail.

    Real response format:
        {
            "status": 0,
            "data": {
                "id": "task-uuid",
                "status": "SUCCESS",
                "image_urls": ["https://..."],
                "image_urls_nowatermark": ["https://..."],
                "image_ratios": ["1024/1024"],
                "generation_options": {"width": 1024, "height": 1024},
                ...
            }
        }

    Args:
        data: The JSON response from the task detail API.

    Returns:
        ImageGenerationResult with extracted image data.
    """
    result = ImageGenerationResult()

    if "data" in data:
        task_data = data["data"]
    else:
        task_data = data

    result.task_id = task_data.get("id") or task_data.get("task_id")

    # Prefer no-watermark URLs, fall back to regular URLs
    nowatermark_urls = task_data.get("image_urls_nowatermark", [])
    regular_urls = task_data.get("image_urls", [])

    urls_to_use = nowatermark_urls if nowatermark_urls else regular_urls
    if isinstance(urls_to_use, list):
        for url in urls_to_use:
            if isinstance(url, str) and url.startswith("http") and url not in result.urls:
                result.urls.append(url)

    # Extract dimensions from generation_options
    gen_opts = task_data.get("generation_options", {})
    if isinstance(gen_opts, dict):
        result.width = gen_opts.get("width")
        result.height = gen_opts.get("height")

    # Also try image_ratios (e.g. "1024/1024")
    if not result.width:
        ratios = task_data.get("image_ratios", [])
        if ratios and isinstance(ratios[0], str) and "/" in ratios[0]:
            try:
                w, h = ratios[0].split("/")
                result.width = int(w)
                result.height = int(h)
            except (ValueError, IndexError):
                pass

    # Fallback: old response formats
    if not result.urls:
        images = task_data.get("images", [])
        if isinstance(images, list):
            for img in images:
                if isinstance(img, str) and img.startswith("http"):
                    result.urls.append(img)
                elif isinstance(img, dict):
                    url = img.get("url") or img.get("image_url") or img.get("src")
                    if url and url not in result.urls:
                        result.urls.append(url)

        # Single image URL fields
        for key in ("image_url", "url", "output_url", "result_url", "output"):
            url = task_data.get(key)
            if url and isinstance(url, str) and url.startswith("http") and url not in result.urls:
                result.urls.append(url)

    # Refined prompt (not always present in task detail)
    result.refined_prompt = task_data.get("refined_prompt") or task_data.get("prompt")

    return result

