"""SSE response parser for Genspark's ask_proxy streaming API.

Confirmed SSE format (from actual API response):

    data: {"id": "uuid", "type": "project_start"}
    data: {"message_id": "uuid", "field_name": "_updatetime", "field_value": "...", "type": "message_field"}
    data: {"message_id": "uuid", "role": "assistant", "project_id": "uuid", "type": "message_start"}
    data: {"message_id": "uuid", "field_name": "content", "field_value": "text chunk", "type": "message_field"}
    data: {"message_id": "uuid", "field_name": "content", "field_value": "more text", "type": "message_field"}
    data: {"type": "project_end"}
"""

import json
import time
from dataclasses import dataclass, field
from typing import Generator, Optional


@dataclass
class ChatChunk:
    """A single chunk from the streaming response."""
    content: str = ""
    role: str = "assistant"
    is_done: bool = False
    project_id: Optional[str] = None
    # Raw metadata from the event
    event_type: str = ""
    raw: Optional[dict] = None


@dataclass
class ChatResponse:
    """Complete parsed chat response."""
    content: str = ""
    role: str = "assistant"
    model: str = ""
    project_id: Optional[str] = None
    usage: Optional[dict] = None
    chunks: list[ChatChunk] = field(default_factory=list)

    def to_openai_format(self) -> dict:
        """Convert to OpenAI-compatible chat completion response format."""
        return {
            "id": f"chatcmpl-genspark-{self.project_id or 'none'}",
            "object": "chat.completion",
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": self.role,
                        "content": self.content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": self.usage or {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }


def parse_sse_line(line: str) -> Optional[dict]:
    """Parse a single SSE data line into a dict.

    SSE format:
        data: {"key": "value"}

    Returns None for non-data lines (comments, empty lines, event names).
    """
    line = line.strip()

    if not line or line.startswith(":"):
        return None

    if line.startswith("data: "):
        data_str = line[6:]  # Remove "data: " prefix
        if data_str == "[DONE]":
            return {"type": "done"}
        try:
            return json.loads(data_str)
        except json.JSONDecodeError:
            # Some lines might be partial JSON or plain text
            return {"type": "text", "content": data_str}

    return None


def parse_sse_stream(raw_text: str) -> Generator[ChatChunk, None, None]:
    """Parse a complete SSE response text into ChatChunk objects.

    Handles the confirmed Genspark SSE format:
    - project_start: conversation ID
    - message_start: assistant message begins
    - message_field with field_name="content": actual text content
    - project_end: conversation complete

    Args:
        raw_text: The full SSE response body as a string.

    Yields:
        ChatChunk objects for each meaningful event.
    """
    for line in raw_text.split("\n"):
        data = parse_sse_line(line)
        if data is None:
            continue

        event_type = data.get("type", "")

        # ── project_start — extract conversation/project ID ──
        if event_type == "project_start":
            pid = data.get("id") or data.get("project_id")
            yield ChatChunk(
                project_id=pid,
                event_type="project_start",
                raw=data,
            )
            continue

        # ── message_start — assistant message begins ──
        if event_type == "message_start":
            pid = data.get("project_id")
            yield ChatChunk(
                project_id=pid,
                role=data.get("role", "assistant"),
                event_type="message_start",
                raw=data,
            )
            continue

        # ── message_field — the actual content chunks ──
        if event_type == "message_field":
            field_name = data.get("field_name", "")
            field_value = data.get("field_value", "")

            if field_name == "content" and field_value:
                yield ChatChunk(
                    content=field_value,
                    event_type="content",
                    raw=data,
                )
            # Skip non-content fields (_updatetime, etc.)
            continue

        # ── project_end — conversation complete ──
        if event_type == "project_end":
            yield ChatChunk(
                is_done=True,
                event_type="project_end",
                raw=data,
            )
            continue

        # ── done signal ──
        if event_type == "done":
            yield ChatChunk(is_done=True, event_type="done")
            continue

        # ── Fallback: try generic content extraction ──
        # Some responses might use different formats
        content = ""
        if "content" in data and isinstance(data["content"], str):
            content = data["content"]
        elif "delta" in data and isinstance(data["delta"], dict):
            content = data["delta"].get("content", "")
        elif "message" in data and isinstance(data["message"], str):
            content = data["message"]
        elif "text" in data and isinstance(data["text"], str):
            content = data["text"]

        if content:
            yield ChatChunk(
                content=content,
                event_type=event_type or "unknown",
                raw=data,
            )

        # Extract project_id if present
        pid = data.get("project_id") or data.get("id")
        if pid and not content:
            yield ChatChunk(
                project_id=pid,
                event_type=event_type or "metadata",
                raw=data,
            )


def parse_sse_to_response(raw_text: str, model: str = "") -> ChatResponse:
    """Parse complete SSE stream into a single ChatResponse.

    Args:
        raw_text: Full SSE response text.
        model: Model name used for the request.

    Returns:
        Complete ChatResponse with assembled content.
    """
    response = ChatResponse(model=model)
    content_parts: list[str] = []

    for chunk in parse_sse_stream(raw_text):
        response.chunks.append(chunk)

        if chunk.content:
            content_parts.append(chunk.content)

        if chunk.project_id:
            response.project_id = chunk.project_id

    response.content = "".join(content_parts)
    return response


def format_sse_chunk_openai(chunk: ChatChunk, model: str = "", chunk_id: str = "") -> str:
    """Format a ChatChunk as an OpenAI-compatible SSE chunk.

    Used by the proxy server to stream responses in OpenAI format.
    """
    if chunk.is_done:
        return "data: [DONE]\n\n"

    data = {
        "id": chunk_id or "chatcmpl-genspark",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": chunk.content} if chunk.content else {},
                "finish_reason": None,
            }
        ],
    }
    return f"data: {json.dumps(data)}\n\n"
