"""Secure filesystem primitives for browser-session data."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path


PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def validate_profile_name(name: str) -> str:
    """Validate a profile identifier before it is used as a path segment."""
    if not isinstance(name, str) or not PROFILE_RE.fullmatch(name):
        raise ValueError(
            f"Invalid profile name '{name}'. "
            "Use alphanumeric characters, hyphens, or underscores."
        )
    return name


def direct_child(root: Path, name: str) -> Path:
    """Return a validated immediate child without following filesystem links."""
    safe_name = validate_profile_name(name)
    resolved_root = Path(root).expanduser().resolve()
    candidate = resolved_root / safe_name
    if candidate.parent != resolved_root:
        raise ValueError(f"Invalid profile name '{name}'.")
    return candidate


def ensure_private_directory(path: Path) -> Path:
    """Create a credential directory and restrict it on POSIX systems."""
    directory = Path(path).expanduser()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        directory.chmod(0o700)
    return directory


def atomic_write_text(path: Path, content: str, mode: int = 0o600) -> None:
    """Atomically replace a text file without exposing partial credentials."""
    destination = Path(path).expanduser()
    ensure_private_directory(destination.parent)
    if destination.is_symlink():
        raise ValueError(f"Refusing to write credential data through symlink: {destination}")

    temporary = destination.parent / (
        f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            if os.name == "posix":
                os.fchmod(handle.fileno(), mode)
        os.replace(temporary, destination)
        if os.name == "posix":
            destination.chmod(mode)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
