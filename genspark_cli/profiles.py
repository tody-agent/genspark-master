"""Multi-account profile management for Genspark CLI.

Directory layout:
    ~/.genspark/
    ├── config.json              # Global settings (default_profile, etc.)
    ├── profiles/
    │   ├── default/
    │   │   ├── session.json
    │   │   ├── storage_state.json
    │   │   └── recaptcha_token.txt
    │   ├── work/
    │   │   └── ...
    │   └── backup/
    │       └── ...
    └── conversations/
        └── ...

On first run, migrates legacy ~/.genspark/session.json → profiles/default/.
"""

import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from .log import log
from .session import SessionManager, SESSION_FILE, STORAGE_STATE_FILE, RECAPTCHA_TOKEN_FILE
from .storage import (
    atomic_write_text,
    direct_child,
    ensure_private_directory,
    validate_profile_name,
)


DEFAULT_BASE_DIR = Path.home() / ".genspark"
CONFIG_FILE = "config.json"
PROFILES_DIR = "profiles"
DEFAULT_PROFILE = "default"


class ProfileManager:
    """Manages multiple named account profiles.

    Each profile is an isolated SessionManager with its own cookies,
    reCAPTCHA tokens, and session metadata.

    Usage:
        pm = ProfileManager()
        session = pm.get_session()           # default profile
        session = pm.get_session("work")     # named profile
        pm.add_profile("backup")             # create new profile slot
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or os.environ.get(
            "GENSPARK_SESSION_DIR", str(DEFAULT_BASE_DIR)
        ))
        ensure_private_directory(self.base_dir)

        self._config_path = self.base_dir / CONFIG_FILE
        self._profiles_dir = self.base_dir / PROFILES_DIR
        self._config: dict = {}

        self._maybe_migrate_legacy()
        self._load_config()

    # ── Migration ────────────────────────────────────────────────────────

    def _maybe_migrate_legacy(self) -> None:
        """Migrate legacy single-account layout to profiles/default/.

        Legacy layout has session.json in base_dir root.
        New layout has session.json inside profiles/default/.
        """
        legacy_session = self.base_dir / SESSION_FILE
        legacy_storage = self.base_dir / STORAGE_STATE_FILE
        legacy_token = self.base_dir / RECAPTCHA_TOKEN_FILE

        # Already migrated — profiles/ dir exists
        if self._profiles_dir.exists():
            return

        # No legacy data — just create profiles dir
        has_legacy = any(f.exists() for f in [legacy_session, legacy_storage, legacy_token])
        if not has_legacy:
            ensure_private_directory(self._profiles_dir)
            return

        # Migrate!
        log.info(
            "Migrating legacy session to profile 'default'",
            extra={"event": "profile_migrate"},
        )

        default_dir = self._profiles_dir / DEFAULT_PROFILE
        ensure_private_directory(default_dir)

        for src_file in [legacy_session, legacy_storage, legacy_token]:
            if src_file.exists():
                dest = default_dir / src_file.name
                shutil.move(str(src_file), str(dest))
                if os.name == "posix":
                    dest.chmod(0o600)
                log.debug("Migrated %s → %s", src_file.name, dest)

        # Also migrate cloak-profile if exists
        cloak_dir = self.base_dir / "cloak-profile"
        if cloak_dir.exists():
            shutil.move(str(cloak_dir), str(default_dir / "cloak-profile"))

        # Write initial config
        self._config = {
            "default_profile": DEFAULT_PROFILE,
            "migrated_at": time.time(),
            "version": "0.3.0",
        }
        self._save_config()
        log.info(
            "Migration complete. Existing session is now profile 'default'.",
            extra={"event": "profile_migrate_done"},
        )

    # ── Config ───────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        """Load global config from config.json."""
        if self._config_path.exists():
            try:
                self._config = json.loads(self._config_path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Failed to load config: %s", exc)
                self._config = {}

        if not self._config:
            self._config = {
                "default_profile": DEFAULT_PROFILE,
                "version": "0.3.0",
            }
            self._save_config()

    def _save_config(self) -> None:
        """Persist global config to disk."""
        self._config["updated_at"] = time.time()
        atomic_write_text(
            self._config_path,
            json.dumps(self._config, indent=2) + "\n",
        )

    # ── Profile CRUD ─────────────────────────────────────────────────────

    @property
    def default_profile(self) -> str:
        """Name of the default profile."""
        return self._config.get("default_profile", DEFAULT_PROFILE)

    @default_profile.setter
    def default_profile(self, name: str) -> None:
        """Set the default profile."""
        if not self._profile_exists(name):
            raise ValueError(f"Profile '{name}' does not exist")
        self._config["default_profile"] = name
        self._save_config()
        log.info("Default profile set to '%s'", name, extra={"event": "profile_switch"})

    def _profile_dir(self, name: str) -> Path:
        """Get the directory path for a named profile."""
        return direct_child(self._profiles_dir, name)

    def _profile_exists(self, name: str) -> bool:
        """Check if a profile directory exists."""
        return self._profile_dir(name).is_dir()

    def list_profiles(self) -> list[dict]:
        """List all profiles with their health status.

        Returns:
            List of dicts: [{name, is_default, is_logged_in, cookie_health}]
        """
        if not self._profiles_dir.exists():
            return []

        profiles = []
        for entry in sorted(self._profiles_dir.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            try:
                validate_profile_name(name)
            except ValueError:
                log.warning("Ignoring unsafe profile directory name: %s", name)
                continue
            session = SessionManager(session_dir=str(entry))
            profiles.append({
                "name": name,
                "is_default": name == self.default_profile,
                "is_logged_in": session.is_logged_in,
                "cookie_health": session.check_cookie_health(),
                "cookie_age": session.get_cookie_age_seconds(),
            })
        return profiles

    def get_session(self, name: Optional[str] = None) -> SessionManager:
        """Get a SessionManager for a named profile.

        Args:
            name: Profile name. None = default profile.

        Returns:
            SessionManager configured for that profile's directory.

        Raises:
            ValueError: If profile doesn't exist.
        """
        name = self.default_profile if name is None else name
        profile_dir = self._profile_dir(name)

        if not profile_dir.exists():
            # Auto-create default profile
            if name == DEFAULT_PROFILE:
                ensure_private_directory(profile_dir)
            else:
                raise ValueError(
                    f"Profile '{name}' does not exist. "
                    f"Create it with: genspark auth add {name}"
                )

        session = SessionManager(session_dir=str(profile_dir))
        session.profile_name = name
        return session

    def add_profile(self, name: str) -> SessionManager:
        """Create a new empty profile.

        Args:
            name: Profile name (alphanumeric + hyphens).

        Returns:
            SessionManager for the new profile (not yet logged in).

        Raises:
            ValueError: If name is invalid or profile already exists.
        """
        validate_profile_name(name)

        if self._profile_exists(name):
            raise ValueError(f"Profile '{name}' already exists")

        profile_dir = self._profile_dir(name)
        ensure_private_directory(profile_dir)

        log.info(
            "Created profile '%s' at %s", name, profile_dir,
            extra={"event": "profile_created"},
        )

        session = SessionManager(session_dir=str(profile_dir))
        session.profile_name = name
        return session

    def remove_profile(self, name: str) -> None:
        """Delete a profile and all its data.

        Args:
            name: Profile name to delete.

        Raises:
            ValueError: If trying to delete default, or profile doesn't exist.
        """
        if name == self.default_profile:
            raise ValueError(
                f"Cannot delete the default profile '{name}'. "
                "Switch default first with: genspark auth switch <other>"
            )

        profile_dir = self._profile_dir(name)
        if not profile_dir.exists():
            raise ValueError(f"Profile '{name}' does not exist")

        profiles_root = self._profiles_dir.resolve()
        if profile_dir.is_symlink() or profile_dir.resolve().parent != profiles_root:
            raise ValueError(f"Unsafe profile path for '{name}'")

        shutil.rmtree(str(profile_dir))
        log.info(
            "Deleted profile '%s'", name,
            extra={"event": "profile_deleted"},
        )

    def get_healthy_profiles(self) -> list[str]:
        """Return names of profiles that are logged in and have fresh/aging cookies.

        Used by AccountRouter to build the failover pool.
        """
        healthy = []
        for p in self.list_profiles():
            if p["is_logged_in"] and p["cookie_health"] in ("fresh", "aging"):
                healthy.append(p["name"])
        return healthy

    def __repr__(self) -> str:
        profiles = self.list_profiles()
        return (
            f"<ProfileManager base={self.base_dir} "
            f"default='{self.default_profile}' "
            f"profiles={len(profiles)}>"
        )
