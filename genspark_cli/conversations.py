"""Conversation persistence and lifecycle management.

Tracks multi-turn conversations with message history, metadata,
and turn counting. Supports conversation listing, resuming,
and forking (creating a new session from a summary).

Storage layout:
    ~/.genspark/conversations/
    ├── index.json               # Quick lookup index
    ├── {project_id_1}.json      # Full conversation data
    ├── {project_id_2}.json
    └── ...
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from .log import log


DEFAULT_BASE_DIR = Path.home() / ".genspark"
CONVERSATIONS_DIR = "conversations"
INDEX_FILE = "index.json"

# Limits
MAX_CONVERSATIONS = 100      # Keep last N, archive older
MAX_MESSAGES_IN_PAYLOAD = 20  # Max messages to send in API payload


@dataclass
class Message:
    """A single message in a conversation."""
    role: str                    # "user", "assistant", "system"
    content: str
    timestamp: float = 0.0
    message_id: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.message_id:
            self.message_id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            role=d.get("role", "user"),
            content=d.get("content", ""),
            timestamp=d.get("timestamp", 0.0),
            message_id=d.get("message_id"),
        )


@dataclass
class Conversation:
    """A tracked conversation with full message history."""
    id: str                           # Genspark project_id or generated UUID
    name: Optional[str] = None        # User-given name
    model: str = ""                   # Model used
    profile: str = "default"          # Account profile used
    created_at: float = 0.0
    last_active: float = 0.0
    turn_count: int = 0               # Number of user messages sent
    messages: list[Message] = field(default_factory=list)
    summary: Optional[str] = None     # Compacted summary
    parent_id: Optional[str] = None   # ID of parent conversation (if forked)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.last_active:
            self.last_active = self.created_at

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        if self.name:
            return self.name
        # Use first user message as preview
        for msg in self.messages:
            if msg.role == "user":
                preview = msg.content[:60]
                if len(msg.content) > 60:
                    preview += "..."
                return preview
        return f"Session {self.id[:8]}"

    @property
    def user_turn_count(self) -> int:
        """Count of user messages (actual conversation turns)."""
        return sum(1 for m in self.messages if m.role == "user")

    def get_messages_for_payload(self, max_messages: int = MAX_MESSAGES_IN_PAYLOAD) -> list[dict]:
        """Get recent messages formatted for Genspark API payload.

        If there's a summary, prepend it as a system message.
        Returns the most recent messages up to max_messages.
        """
        payload_messages = []

        # If we have a summary from a previous compaction, add as system context
        if self.summary:
            payload_messages.append({
                "role": "user",
                "id": str(uuid.uuid4()),
                "content": (
                    f"[Previous conversation context]\n{self.summary}\n\n"
                    "[Continue from here]"
                ),
            })

        # Get recent messages
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        for msg in recent:
            payload_messages.append({
                "role": msg.role,
                "id": msg.message_id or str(uuid.uuid4()),
                "content": msg.content,
            })

        return payload_messages

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "profile": self.profile,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "turn_count": self.turn_count,
            "messages": [m.to_dict() for m in self.messages],
            "summary": self.summary,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Conversation":
        messages = [Message.from_dict(m) for m in d.get("messages", [])]
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name"),
            model=d.get("model", ""),
            profile=d.get("profile", "default"),
            created_at=d.get("created_at", 0.0),
            last_active=d.get("last_active", 0.0),
            turn_count=d.get("turn_count", 0),
            messages=messages,
            summary=d.get("summary"),
            parent_id=d.get("parent_id"),
        )

    def to_index_entry(self) -> dict:
        """Compact representation for the index file."""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "model": self.model,
            "profile": self.profile,
            "turn_count": self.turn_count,
            "last_active": self.last_active,
            "created_at": self.created_at,
            "has_summary": self.summary is not None,
        }


class ConversationStore:
    """Manages conversation persistence on disk.

    Usage:
        store = ConversationStore()
        conv = store.create(model="claude-opus-4-6", profile="default")
        store.add_turn(conv.id, "user", "Hello!")
        store.add_turn(conv.id, "assistant", "Hi there!")
        store.save(conv)

        # Later:
        conversations = store.list_recent(limit=10)
        conv = store.get(conv.id)
    """

    def __init__(self, base_dir: Optional[str] = None):
        base = Path(base_dir or os.environ.get(
            "GENSPARK_SESSION_DIR", str(DEFAULT_BASE_DIR)
        ))
        self._dir = base / CONVERSATIONS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / INDEX_FILE
        self._index: list[dict] = []
        self._cache: dict[str, Conversation] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load conversation index from disk."""
        if self._index_path.exists():
            try:
                self._index = json.loads(self._index_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._index = []

    def _save_index(self) -> None:
        """Persist conversation index to disk."""
        self._index_path.write_text(json.dumps(self._index, indent=2))

    def _conv_path(self, conv_id: str) -> Path:
        """File path for a conversation's full data."""
        # Sanitize ID for filesystem
        safe_id = conv_id.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe_id}.json"

    # ── CRUD ─────────────────────────────────────────────────────────────

    def create(
        self,
        model: str = "",
        profile: str = "default",
        name: Optional[str] = None,
        summary: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            model: AI model being used.
            profile: Account profile name.
            name: Optional human-readable name.
            summary: Optional initial context (from compaction).
            parent_id: Optional parent conversation ID (if forked).

        Returns:
            New Conversation object (persisted to disk).
        """
        conv = Conversation(
            id=str(uuid.uuid4()),
            name=name,
            model=model,
            profile=profile,
            summary=summary,
            parent_id=parent_id,
        )
        self._save_conversation(conv)
        self._update_index(conv)
        self._enforce_limit()

        log.debug(
            "Created conversation '%s' (model=%s, profile=%s)",
            conv.id[:8], model, profile,
            extra={"event": "conversation_created"},
        )
        return conv

    def get(self, conv_id: str) -> Optional[Conversation]:
        """Load a conversation by ID.

        Returns None if not found.
        """
        # Check cache first
        if conv_id in self._cache:
            return self._cache[conv_id]

        path = self._conv_path(conv_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            conv = Conversation.from_dict(data)
            self._cache[conv_id] = conv
            return conv
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to load conversation %s: %s", conv_id[:8], exc)
            return None

    def save(self, conv: Conversation) -> None:
        """Persist a conversation to disk and update index."""
        self._save_conversation(conv)
        self._update_index(conv)

    def _save_conversation(self, conv: Conversation) -> None:
        """Write conversation data to its JSON file."""
        path = self._conv_path(conv.id)
        path.write_text(json.dumps(conv.to_dict(), indent=2, ensure_ascii=False))
        self._cache[conv.id] = conv

    def _update_index(self, conv: Conversation) -> None:
        """Update the conversation's entry in the index."""
        entry = conv.to_index_entry()

        # Replace existing or append
        self._index = [e for e in self._index if e.get("id") != conv.id]
        self._index.append(entry)

        # Sort by last_active (most recent first)
        self._index.sort(key=lambda e: e.get("last_active", 0), reverse=True)
        self._save_index()

    # ── Turn Management ──────────────────────────────────────────────────

    def add_turn(self, conv_id: str, role: str, content: str) -> Optional[Conversation]:
        """Add a message to a conversation and persist.

        Args:
            conv_id: Conversation ID.
            role: "user" or "assistant".
            content: Message content.

        Returns:
            Updated Conversation, or None if not found.
        """
        conv = self.get(conv_id)
        if not conv:
            return None

        msg = Message(role=role, content=content)
        conv.messages.append(msg)
        conv.last_active = time.time()

        if role == "user":
            conv.turn_count += 1

        self.save(conv)
        return conv

    def set_project_id(self, conv_id: str, project_id: str) -> None:
        """Update the Genspark project_id for a conversation.

        Called when we get a project_start event from the API.
        """
        conv = self.get(conv_id)
        if conv and conv.id != project_id:
            # The API assigned a different project_id
            old_id = conv.id
            conv_data = conv.to_dict()
            conv_data["id"] = project_id

            # Remove old file and index entry
            old_path = self._conv_path(old_id)
            if old_path.exists():
                old_path.unlink()
            if old_id in self._cache:
                del self._cache[old_id]
            self._index = [e for e in self._index if e.get("id") != old_id]

            # Save with new ID
            new_conv = Conversation.from_dict(conv_data)
            self.save(new_conv)

    # ── Listing ──────────────────────────────────────────────────────────

    def list_recent(self, limit: int = 10) -> list[dict]:
        """List most recent conversations (from index).

        Returns:
            List of index entries sorted by last_active descending.
        """
        return self._index[:limit]

    def list_all(self) -> list[dict]:
        """List all conversations from index."""
        return list(self._index)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Simple search across conversation names and first messages."""
        query_lower = query.lower()
        results = []
        for entry in self._index:
            display = entry.get("display_name", "").lower()
            name = (entry.get("name") or "").lower()
            if query_lower in display or query_lower in name:
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    # ── Compaction & Forking ─────────────────────────────────────────────

    def set_summary(self, conv_id: str, summary: str) -> Optional[Conversation]:
        """Store a compacted summary for a conversation.

        Args:
            conv_id: Conversation ID.
            summary: The summary text.

        Returns:
            Updated Conversation, or None.
        """
        conv = self.get(conv_id)
        if not conv:
            return None
        conv.summary = summary
        self.save(conv)
        return conv

    def fork(
        self,
        parent_id: str,
        summary: str,
        model: Optional[str] = None,
        profile: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Conversation]:
        """Fork a conversation — create a new one with summary as initial context.

        Args:
            parent_id: ID of the parent conversation.
            summary: Summary of the parent conversation.
            model: Model for the new conversation (default: same as parent).
            profile: Profile for the new conversation (default: same as parent).
            name: Optional name for the new conversation.

        Returns:
            New Conversation with summary as context, or None if parent not found.
        """
        parent = self.get(parent_id)
        if not parent:
            return None

        new_name = name or f"Continued from: {parent.display_name[:40]}"
        new_conv = self.create(
            model=model or parent.model,
            profile=profile or parent.profile,
            name=new_name,
            summary=summary,
            parent_id=parent_id,
        )

        log.info(
            "Forked conversation %s → %s",
            parent_id[:8], new_conv.id[:8],
            extra={"event": "conversation_forked"},
        )
        return new_conv

    # ── Deletion ─────────────────────────────────────────────────────────

    def delete(self, conv_id: str) -> bool:
        """Delete a conversation.

        Returns True if deleted, False if not found.
        """
        path = self._conv_path(conv_id)
        if path.exists():
            path.unlink()

        if conv_id in self._cache:
            del self._cache[conv_id]

        old_len = len(self._index)
        self._index = [e for e in self._index if e.get("id") != conv_id]

        if len(self._index) != old_len:
            self._save_index()
            log.debug("Deleted conversation %s", conv_id[:8])
            return True
        return False

    # ── Housekeeping ─────────────────────────────────────────────────────

    def _enforce_limit(self) -> None:
        """Remove oldest conversations if we exceed MAX_CONVERSATIONS."""
        if len(self._index) <= MAX_CONVERSATIONS:
            return

        # Remove oldest entries
        to_remove = self._index[MAX_CONVERSATIONS:]
        self._index = self._index[:MAX_CONVERSATIONS]

        for entry in to_remove:
            cid = entry.get("id", "")
            path = self._conv_path(cid)
            if path.exists():
                path.unlink()
            if cid in self._cache:
                del self._cache[cid]

        self._save_index()
        log.info(
            "Cleaned up %d old conversations (limit=%d)",
            len(to_remove), MAX_CONVERSATIONS,
            extra={"event": "conversation_cleanup"},
        )

    @property
    def count(self) -> int:
        """Number of tracked conversations."""
        return len(self._index)

    def __repr__(self) -> str:
        return f"<ConversationStore dir={self._dir} conversations={self.count}>"
