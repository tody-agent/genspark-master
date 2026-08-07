"""Custom exception hierarchy for Genspark CLI.

Structured exceptions allow callers to handle specific failures:
  - AuthenticationError  → session expired, need re-login
  - RateLimitError       → Genspark throttled us
  - APIError             → unexpected API response
  - SessionExpiredError  → cookies are stale
  - ModelNotFoundError   → invalid model name
  - NetworkError         → connection / DNS / timeout issues
  - ParseError           → SSE stream parsing failed
"""


class GensparkError(Exception):
    """Base exception for all Genspark CLI errors."""

    def __init__(self, message: str, *, details: str = "", suggestion: str = ""):
        self.details = details
        self.suggestion = suggestion
        full = message
        if details:
            full += f"\n  Details: {details}"
        if suggestion:
            full += f"\n  Suggestion: {suggestion}"
        super().__init__(full)


# ── Authentication ───────────────────────────────────────────────────────

class AuthenticationError(GensparkError):
    """Login is required or current session is invalid."""

    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(
            message,
            suggestion=kwargs.pop("suggestion", "Run: genspark auth login"),
            **kwargs,
        )


class SessionExpiredError(AuthenticationError):
    """Saved cookies have expired and need refreshing."""

    def __init__(self, message: str = "Session expired — cookies are stale", **kwargs):
        super().__init__(
            message,
            suggestion=kwargs.pop("suggestion", "Run: genspark auth login  (to refresh cookies)"),
            **kwargs,
        )


# ── API ──────────────────────────────────────────────────────────────────

class APIError(GensparkError):
    """Genspark API returned an unexpected response."""

    def __init__(self, message: str, *, status_code: int = 0, body: str = "", **kwargs):
        self.status_code = status_code
        self.body = body
        details = kwargs.pop("details", "")
        if status_code:
            details = f"HTTP {status_code}. {details}".strip()
        super().__init__(message, details=details, **kwargs)


class RateLimitError(APIError):
    """Genspark is throttling our requests (HTTP 429 or similar)."""

    def __init__(self, message: str = "Rate limited by Genspark", **kwargs):
        super().__init__(
            message,
            suggestion=kwargs.pop("suggestion", "Wait a few minutes and try again, or switch to a different model."),
            **kwargs,
        )


class RecaptchaError(APIError):
    """reCAPTCHA challenge blocked the request.

    This means session cookies alone are insufficient and a fresh
    browser-generated token is needed.
    """

    def __init__(self, message: str = "reCAPTCHA challenge required", **kwargs):
        super().__init__(
            message,
            suggestion=kwargs.pop(
                "suggestion",
                "Run: genspark auth login  (to refresh reCAPTCHA session)",
            ),
            **kwargs,
        )


# ── Network ──────────────────────────────────────────────────────────────

class NetworkError(GensparkError):
    """Connection, DNS, or timeout failure talking to Genspark."""

    def __init__(self, message: str = "Network error", **kwargs):
        super().__init__(
            message,
            suggestion=kwargs.pop("suggestion", "Check your internet connection and try again."),
            **kwargs,
        )


class TimeoutError(NetworkError):
    """Request timed out waiting for Genspark response."""

    def __init__(self, message: str = "Request timed out", *, timeout_seconds: float = 0, **kwargs):
        self.timeout_seconds = timeout_seconds
        details = kwargs.pop("details", "")
        if timeout_seconds:
            details = f"Timeout after {timeout_seconds}s. {details}".strip()
        super().__init__(message, details=details, **kwargs)


# ── Model ────────────────────────────────────────────────────────────────

class ModelNotFoundError(GensparkError):
    """Requested model is not in our registry."""

    def __init__(self, model_name: str, available: list[str] | None = None, **kwargs):
        self.model_name = model_name
        msg = f"Unknown model: '{model_name}'"
        if available:
            msg += f".  Available: {', '.join(available[:6])}..."
        super().__init__(msg, **kwargs)


# ── Parsing ──────────────────────────────────────────────────────────────

class ParseError(GensparkError):
    """Failed to parse SSE stream or API response."""

    def __init__(self, message: str = "Failed to parse API response", **kwargs):
        super().__init__(
            message,
            suggestion=kwargs.pop("suggestion", "The API response format may have changed. Try updating genspark-cli."),
            **kwargs,
        )
