"""Structured logging for Genspark CLI.

Provides a consistent logger with:
  - Console output (Rich-formatted) for user-facing messages
  - File output (JSON lines) for debugging
  - Environment variable control:
      GENSPARK_LOG_LEVEL  — DEBUG / INFO / WARNING / ERROR (default: WARNING)
      GENSPARK_LOG_FILE   — path to write JSON logs (default: ~/.genspark/genspark.log)
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any


# ── Log directory ────────────────────────────────────────────────────────

_LOG_DIR = Path.home() / ".genspark"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_DEFAULT_LOG_FILE = _LOG_DIR / "genspark.log"
_DEFAULT_LEVEL = "WARNING"


# ── JSON Formatter ───────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects (for machine parsing)."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        # Attach extra fields (e.g., model, status_code)
        for key in ("model", "status_code", "url", "duration_ms", "project_id", "event"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry, ensure_ascii=False)


# ── Console Formatter ────────────────────────────────────────────────────

class ConsoleFormatter(logging.Formatter):
    """Compact coloured output for stderr (only WARNING+)."""

    COLORS = {
        "DEBUG": "\033[90m",    # grey
        "INFO": "\033[36m",     # cyan
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        prefix = f"{color}[{record.levelname}]{self.RESET}"
        return f"{prefix} {record.getMessage()}"


# ── Logger Factory ───────────────────────────────────────────────────────

def _build_logger() -> logging.Logger:
    """Create the package-level logger with console + file handlers."""
    logger = logging.getLogger("genspark")
    if logger.handlers:
        return logger  # already configured

    env_level = os.environ.get("GENSPARK_LOG_LEVEL", _DEFAULT_LEVEL).upper()
    level = getattr(logging, env_level, logging.WARNING)
    logger.setLevel(logging.DEBUG)  # capture everything; handlers filter

    # ── File handler (DEBUG+) ──
    log_file = Path(os.environ.get("GENSPARK_LOG_FILE", str(_DEFAULT_LOG_FILE)))
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(JSONFormatter())
    logger.addHandler(fh)

    # ── Console handler (respects GENSPARK_LOG_LEVEL) ──
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(ConsoleFormatter())
    logger.addHandler(ch)

    return logger


# ── Public API ───────────────────────────────────────────────────────────

log = _build_logger()
"""Package-wide logger instance.

Usage:
    from genspark_cli.log import log

    log.debug("Sending request", extra={"url": url, "model": "gpt-5.4"})
    log.info("Response received in %dms", elapsed_ms)
    log.warning("Session might be expiring soon")
    log.error("API returned %d", status, extra={"status_code": status})
"""


def set_level(level_name: str) -> None:
    """Change console log level at runtime (e.g. --verbose flag)."""
    level = getattr(logging, level_name.upper(), logging.WARNING)
    for h in log.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(level)
