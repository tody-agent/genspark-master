"""Session management — persist cookies and browser state across invocations.

Stores browser cookies + localStorage in ~/.genspark/ so the user only
needs to login once via `genspark auth login`.

Enhanced for Cookie-Relay architecture:
  - get_cookies_dict() → flat dict for httpx requests
  - Cookie age tracking and expiry warnings
  - Profile support for multiple accounts
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from .log import log
from .storage import atomic_write_text, ensure_private_directory


DEFAULT_SESSION_DIR = Path.home() / ".genspark"
SESSION_FILE = "session.json"
STORAGE_STATE_FILE = "storage_state.json"
RECAPTCHA_TOKEN_FILE = "recaptcha_token.txt"

# Cookies critical for Genspark auth
AUTH_COOKIES = {"gslogin", "ai_session", "ai_user", "snexid"}

# Warn if cookies are older than this (seconds)
COOKIE_WARN_AGE = 7 * 24 * 3600    # 7 days
COOKIE_EXPIRY_AGE = 30 * 24 * 3600  # 30 days


class SessionManager:
    """Manages browser session persistence for Genspark CLI."""

    def __init__(self, session_dir: Optional[str] = None):
        self.session_dir = Path(session_dir or os.environ.get(
            "GENSPARK_SESSION_DIR", str(DEFAULT_SESSION_DIR)
        ))
        ensure_private_directory(self.session_dir)

        self._session_path = self.session_dir / SESSION_FILE
        self._storage_state_path = self.session_dir / STORAGE_STATE_FILE
        self._data: dict[str, Any] = {}
        self._profile_name: str = "default"
        self._load()

    @property
    def profile_name(self) -> str:
        """Name of the account profile this session belongs to."""
        return self._profile_name

    @profile_name.setter
    def profile_name(self, value: str) -> None:
        self._profile_name = value

    def _load(self) -> None:
        """Load session data from disk."""
        if self._session_path.exists():
            try:
                self._data = json.loads(self._session_path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Failed to load session file: %s", exc)
                self._data = {}

    def _save(self) -> None:
        """Persist session data to disk."""
        self._data["updated_at"] = time.time()
        atomic_write_text(self._session_path, json.dumps(self._data, indent=2) + "\n")

    # ── Storage State (Playwright format) ────────────────────────────────

    @property
    def storage_state_path(self) -> Path:
        """Path to Playwright storage state file (cookies + localStorage)."""
        return self._storage_state_path

    def has_storage_state(self) -> bool:
        """Check if a saved Playwright storage state exists."""
        return self._storage_state_path.exists()

    def save_storage_state(self, state: dict) -> None:
        """Save Playwright storage state (from context.storage_state())."""
        atomic_write_text(
            self._storage_state_path,
            json.dumps(state, indent=2) + "\n",
        )
        self._data["storage_state_saved_at"] = time.time()
        self._save()
        log.debug(
            "Storage state saved (%d cookies)",
            len(state.get("cookies", [])),
            extra={"event": "session_saved"},
        )

    def load_storage_state(self) -> Optional[dict]:
        """Load Playwright storage state, or None if not found."""
        if not self._storage_state_path.exists():
            return None
        try:
            return json.loads(self._storage_state_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to load storage state: %s", exc)
            return None

    # ── Cookie Extraction (for httpx) ────────────────────────────────────

    # ── reCAPTCHA Token ───────────────────────────────────────────────────

    def save_recaptcha_token(self, token: str) -> None:
        """Persist a reCAPTCHA token for reuse across httpx requests."""
        token_path = self.session_dir / RECAPTCHA_TOKEN_FILE
        atomic_write_text(token_path, token)
        self._data["recaptcha_token_saved_at"] = time.time()
        self._save()
        log.debug("reCAPTCHA token saved (%d chars)", len(token), extra={"event": "recaptcha_saved"})

    def get_recaptcha_token(self) -> Optional[str]:
        """Load the persisted reCAPTCHA token, or None."""
        token_path = self.session_dir / RECAPTCHA_TOKEN_FILE
        if not token_path.exists():
            return None
        token = token_path.read_text().strip()
        if not token:
            return None
        return token

    def get_recaptcha_token_age(self) -> Optional[float]:
        """Return age of reCAPTCHA token in seconds, or None."""
        saved_at = self._data.get("recaptcha_token_saved_at")
        if saved_at:
            return time.time() - saved_at
        return None

    # ── Cookie Extraction (for httpx) ────────────────────────────────────

    def get_cookies_dict(self) -> dict[str, str]:
        """Extract cookies as a flat {name: value} dict for httpx.

        Returns:
            Dict of cookie name → value.  Empty dict if no session.
        """
        state = self.load_storage_state()
        if not state:
            log.debug("No storage state found — empty cookies", extra={"event": "no_cookies"})
            return {}

        cookies = {}
        for c in state.get("cookies", []):
            name = c.get("name", "")
            value = c.get("value", "")
            if name and value:
                cookies[name] = value

        if not cookies:
            log.warning("Storage state exists but contains no cookies")
        else:
            log.debug("Loaded %d cookies from storage state", len(cookies))

        return cookies

    def get_cookie_age_seconds(self) -> Optional[float]:
        """Return age of cookies in seconds, or None if unknown."""
        saved_at = self._data.get("storage_state_saved_at")
        if saved_at:
            return time.time() - saved_at
        return None

    def check_cookie_health(self) -> str:
        """Check cookie freshness and return a status string.

        Returns:
            "fresh" | "aging" | "expired" | "missing"
        """
        if not self.has_storage_state():
            return "missing"

        age = self.get_cookie_age_seconds()
        if age is None:
            return "fresh"  # unknown age — assume ok

        if age > COOKIE_EXPIRY_AGE:
            log.warning(
                "Cookies are %d days old — likely expired",
                int(age / 86400),
                extra={"event": "cookie_expired"},
            )
            return "expired"
        elif age > COOKIE_WARN_AGE:
            log.info(
                "Cookies are %d days old — may expire soon",
                int(age / 86400),
                extra={"event": "cookie_aging"},
            )
            return "aging"

        return "fresh"

    # ── Session Metadata ─────────────────────────────────────────────────

    @property
    def is_logged_in(self) -> bool:
        """Check if we have a valid login session."""
        state = self.load_storage_state()
        if not state:
            return False
        cookies = {c.get("name") for c in state.get("cookies", [])}
        # Must have at least some auth cookies
        return bool(cookies & AUTH_COOKIES)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a session value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a session value and persist."""
        self._data[key] = value
        self._save()

    @property
    def last_project_id(self) -> Optional[str]:
        """Last conversation project_id for continuing chats."""
        return self._data.get("last_project_id")

    @last_project_id.setter
    def last_project_id(self, value: str) -> None:
        self._data["last_project_id"] = value
        self._save()

    def clear(self) -> None:
        """Clear all session data."""
        self._data = {}
        token_path = self.session_dir / RECAPTCHA_TOKEN_FILE
        for f in [self._session_path, self._storage_state_path, token_path]:
            if f.exists():
                f.unlink()
        log.info("Session cleared", extra={"event": "session_cleared"})

    def __repr__(self) -> str:
        status = "logged_in" if self.is_logged_in else "not_logged_in"
        health = self.check_cookie_health()
        return f"<SessionManager dir={self.session_dir} status={status} cookies={health}>"
