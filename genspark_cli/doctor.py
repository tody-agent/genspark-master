"""Offline installation and browser-session diagnostics."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .session import AUTH_COOKIES, DEFAULT_SESSION_DIR


def _module_check(module: str, *, optional: bool = True) -> dict[str, Any]:
    available = importlib.util.find_spec(module) is not None
    if available:
        return {"status": "ok", "available": True}
    return {
        "status": "optional_missing" if optional else "error",
        "available": False,
    }


def _profile_directories(root: Path) -> list[Path]:
    profiles_root = root / "profiles"
    if profiles_root.is_dir():
        return sorted(path for path in profiles_root.iterdir() if path.is_dir())
    return [root] if root.is_dir() else []


def _browser_session_check(root: Path) -> dict[str, Any]:
    valid_profiles: list[str] = []
    incomplete_profiles: list[str] = []

    for profile_dir in _profile_directories(root):
        storage_path = profile_dir / "storage_state.json"
        token_path = profile_dir / "recaptcha_token.txt"
        if not storage_path.is_file():
            continue
        try:
            state = json.loads(storage_path.read_text(encoding="utf-8"))
            cookie_names = {
                item.get("name") for item in state.get("cookies", []) if isinstance(item, dict)
            }
            has_auth_cookie = bool(cookie_names & AUTH_COOKIES)
            has_token = token_path.is_file() and bool(token_path.read_text(encoding="utf-8").strip())
        except (OSError, json.JSONDecodeError):
            has_auth_cookie = False
            has_token = False

        if has_auth_cookie and has_token:
            valid_profiles.append(profile_dir.name)
        else:
            incomplete_profiles.append(profile_dir.name)

    if valid_profiles:
        return {
            "status": "ok",
            "profiles": valid_profiles,
            "incomplete_profiles": incomplete_profiles,
        }
    return {
        "status": "missing",
        "profiles": [],
        "incomplete_profiles": incomplete_profiles,
        "suggestion": "Run: genspark auth login",
    }


def run_doctor(session_dir: str | None = None) -> dict[str, Any]:
    """Inspect local requirements without contacting Genspark."""
    root = Path(
        session_dir
        or os.environ.get("GENSPARK_SESSION_DIR")
        or DEFAULT_SESSION_DIR
    ).expanduser()
    package_root = Path(__file__).resolve().parent.parent

    checks: dict[str, dict[str, Any]] = {
        "python": {
            "status": "ok" if sys.version_info >= (3, 10) else "error",
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "required": ">=3.10",
        },
        "package": {"status": "ok", "version": __version__},
        "browser_session": _browser_session_check(root),
        "playwright": _module_check("playwright"),
        "mcp": _module_check("mcp"),
        "plugin_manifest": {
            "status": "ok" if (package_root / ".codex-plugin" / "plugin.json").is_file() else "not_applicable",
        },
        "network": {
            "status": "not_checked",
            "reason": "doctor is intentionally offline",
        },
    }

    if any(check["status"] == "error" for check in checks.values()):
        status = "error"
    elif checks["browser_session"]["status"] != "ok":
        status = "degraded"
    else:
        status = "ok"

    return {
        "schema_version": 1,
        "status": status,
        "authentication": "browser_session",
        "session_dir": str(root),
        "checks": checks,
    }
