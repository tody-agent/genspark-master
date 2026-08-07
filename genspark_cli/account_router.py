"""Intelligent account routing with failover and circuit breaker.

Routes requests through a pool of authenticated Genspark profiles.
When one account fails (rate-limited, expired, reCAPTCHA blocked),
automatically switches to the next healthy account.

Circuit Breaker Pattern:
    - On failure → mark account as unhealthy with cooldown timer
    - After cooldown expires → re-test the account (half-open state)
    - On success after cooldown → mark healthy again

Usage:
    router = AccountRouter(profile_manager)
    session = router.get_session()  # best available
    try:
        result = do_chat(session, ...)
    except (SessionExpiredError, RateLimitError, RecaptchaError):
        router.mark_unhealthy(session.profile_name, cooldown=300)
        session = router.get_session()  # next available
        result = do_chat(session, ...)
"""

import time
from dataclasses import dataclass, field
from typing import Optional

from .log import log
from .profiles import ProfileManager
from .session import SessionManager


# ── Account Health States ────────────────────────────────────────────────

HEALTH_HEALTHY = "healthy"
HEALTH_COOLDOWN = "cooldown"
HEALTH_EXPIRED = "expired"
HEALTH_NEEDS_LOGIN = "needs_login"

# Default cooldown periods (seconds)
DEFAULT_COOLDOWN = 300       # 5 minutes after RateLimit
RECAPTCHA_COOLDOWN = 600     # 10 minutes after reCAPTCHA failure
EXPIRED_COOLDOWN = 3600      # 1 hour after session expired (needs re-login)


@dataclass
class AccountStatus:
    """Track health and usage statistics for one account."""

    profile_name: str
    health: str = HEALTH_HEALTHY
    unhealthy_at: Optional[float] = None
    cooldown_until: Optional[float] = None
    failure_reason: str = ""
    failure_count: int = 0
    success_count: int = 0
    last_used_at: Optional[float] = None
    total_requests: int = 0

    @property
    def is_available(self) -> bool:
        """Check if this account is available for requests."""
        if self.health == HEALTH_HEALTHY:
            return True
        if self.health == HEALTH_COOLDOWN and self.cooldown_until:
            # Cooldown expired → half-open, allow retry
            if time.time() >= self.cooldown_until:
                return True
        return False

    @property
    def cooldown_remaining(self) -> Optional[float]:
        """Seconds remaining in cooldown, or None if not in cooldown."""
        if self.cooldown_until:
            remaining = self.cooldown_until - time.time()
            return max(0, remaining) if remaining > 0 else None
        return None


class AccountRouter:
    """Routes requests through a pool of accounts with failover.

    Usage:
        router = AccountRouter(profile_manager)
        session = router.get_session()
        # ... use session for chat ...
        router.mark_success(session.profile_name)
        # or on failure:
        router.mark_unhealthy(session.profile_name, cooldown=300)
        session = router.get_session()  # failover to next
    """

    def __init__(self, profiles: ProfileManager):
        self.profiles = profiles
        self._accounts: dict[str, AccountStatus] = {}
        self._last_used_index = -1
        self._refresh_pool()

    def _refresh_pool(self) -> None:
        """Sync account pool with available profiles."""
        for p in self.profiles.list_profiles():
            name = p["name"]
            if name not in self._accounts:
                health = HEALTH_HEALTHY
                if not p["is_logged_in"]:
                    health = HEALTH_NEEDS_LOGIN
                elif p["cookie_health"] == "expired":
                    health = HEALTH_EXPIRED
                self._accounts[name] = AccountStatus(
                    profile_name=name,
                    health=health,
                )

        # Remove accounts whose profiles were deleted
        existing = {p["name"] for p in self.profiles.list_profiles()}
        for name in list(self._accounts):
            if name not in existing:
                del self._accounts[name]

    # ── Session Selection ────────────────────────────────────────────────

    def get_session(self, preferred: Optional[str] = None) -> SessionManager:
        """Get the best available session, with failover.

        Selection order:
            1. Preferred profile (if specified and available)
            2. Default profile (if available)
            3. Next available profile (round-robin among healthy ones)

        Args:
            preferred: Optional profile name to prefer.

        Returns:
            SessionManager for the selected account.

        Raises:
            RuntimeError: If no accounts are available.
        """
        self._refresh_pool()

        # 1. Try preferred
        if preferred and self._is_available(preferred):
            return self._use(preferred)

        # 2. Try default
        default = self.profiles.default_profile
        if self._is_available(default):
            return self._use(default)

        # 3. Round-robin through available accounts
        available = [
            name for name, status in self._accounts.items()
            if status.is_available
        ]

        if not available:
            # Check if some are in cooldown and will be available soon
            cooldown_accounts = [
                (name, status.cooldown_remaining)
                for name, status in self._accounts.items()
                if status.health == HEALTH_COOLDOWN and status.cooldown_remaining
            ]
            if cooldown_accounts:
                soonest = min(cooldown_accounts, key=lambda x: x[1])
                raise RuntimeError(
                    f"All accounts are in cooldown. "
                    f"'{soonest[0]}' will be available in {int(soonest[1])}s. "
                    f"Or add another account: genspark auth add <name>"
                )

            needs_login = [
                name for name, status in self._accounts.items()
                if status.health in (HEALTH_NEEDS_LOGIN, HEALTH_EXPIRED)
            ]
            if needs_login:
                raise RuntimeError(
                    f"No healthy accounts. These need re-login: {', '.join(needs_login)}. "
                    f"Run: genspark auth refresh <name>"
                )

            raise RuntimeError(
                "No accounts available. Run: genspark auth login  "
                "or  genspark auth add <name>"
            )

        # Round-robin
        self._last_used_index = (self._last_used_index + 1) % len(available)
        chosen = available[self._last_used_index]
        return self._use(chosen)

    def _is_available(self, name: str) -> bool:
        """Check if a named account is available."""
        status = self._accounts.get(name)
        if not status:
            return False
        return status.is_available

    def _use(self, name: str) -> SessionManager:
        """Select an account for use, update tracking."""
        status = self._accounts[name]
        status.last_used_at = time.time()
        status.total_requests += 1

        if status.health == HEALTH_COOLDOWN:
            # Half-open: cooldown expired, trying again
            log.info(
                "Cooldown expired for '%s' — retrying (half-open)",
                name,
                extra={"event": "account_halfopen", "profile": name},
            )

        session = self.profiles.get_session(name)
        log.debug(
            "Using account '%s' (total requests: %d)",
            name, status.total_requests,
            extra={"event": "account_selected", "profile": name},
        )
        return session

    # ── Health Management ────────────────────────────────────────────────

    def mark_success(self, name: str) -> None:
        """Mark an account as healthy after successful request."""
        status = self._accounts.get(name)
        if not status:
            return

        was_unhealthy = status.health != HEALTH_HEALTHY
        status.health = HEALTH_HEALTHY
        status.success_count += 1
        status.failure_count = 0
        status.cooldown_until = None
        status.unhealthy_at = None
        status.failure_reason = ""

        if was_unhealthy:
            log.info(
                "Account '%s' recovered — marked healthy",
                name,
                extra={"event": "account_recovered", "profile": name},
            )

    def mark_unhealthy(
        self,
        name: str,
        reason: str = "unknown",
        cooldown: Optional[float] = None,
    ) -> None:
        """Mark an account as unhealthy with a cooldown period.

        Args:
            name: Profile name.
            reason: Why the account failed (for logging).
            cooldown: Cooldown seconds. None = use default based on reason.
        """
        status = self._accounts.get(name)
        if not status:
            return

        if cooldown is None:
            # Auto-detect cooldown based on reason
            if "rate" in reason.lower():
                cooldown = DEFAULT_COOLDOWN
            elif "recaptcha" in reason.lower():
                cooldown = RECAPTCHA_COOLDOWN
            elif "expired" in reason.lower() or "auth" in reason.lower():
                cooldown = EXPIRED_COOLDOWN
            else:
                cooldown = DEFAULT_COOLDOWN

        status.health = HEALTH_COOLDOWN
        status.unhealthy_at = time.time()
        status.cooldown_until = time.time() + cooldown
        status.failure_reason = reason
        status.failure_count += 1

        log.warning(
            "Account '%s' marked unhealthy: %s (cooldown %ds, failures: %d)",
            name, reason, int(cooldown), status.failure_count,
            extra={
                "event": "account_unhealthy",
                "profile": name,
                "reason": reason,
                "cooldown": cooldown,
            },
        )

    def mark_needs_login(self, name: str) -> None:
        """Mark an account as needing re-authentication."""
        status = self._accounts.get(name)
        if not status:
            return
        status.health = HEALTH_NEEDS_LOGIN
        status.failure_reason = "needs re-login"
        log.warning(
            "Account '%s' needs re-login",
            name,
            extra={"event": "account_needs_login", "profile": name},
        )

    # ── Status ───────────────────────────────────────────────────────────

    def get_status(self) -> list[dict]:
        """Get status of all accounts in the pool.

        Returns:
            List of dicts with account health information.
        """
        self._refresh_pool()
        statuses = []
        for name, status in sorted(self._accounts.items()):
            entry = {
                "name": name,
                "health": status.health,
                "is_available": status.is_available,
                "is_default": name == self.profiles.default_profile,
                "success_count": status.success_count,
                "failure_count": status.failure_count,
                "total_requests": status.total_requests,
            }
            if status.cooldown_remaining:
                entry["cooldown_remaining_s"] = int(status.cooldown_remaining)
            if status.failure_reason:
                entry["failure_reason"] = status.failure_reason
            statuses.append(entry)
        return statuses

    @property
    def pool_size(self) -> int:
        """Total number of accounts in the pool."""
        return len(self._accounts)

    @property
    def available_count(self) -> int:
        """Number of currently available accounts."""
        return sum(1 for s in self._accounts.values() if s.is_available)

    def __repr__(self) -> str:
        return (
            f"<AccountRouter pool={self.pool_size} "
            f"available={self.available_count} "
            f"default='{self.profiles.default_profile}'>"
        )
