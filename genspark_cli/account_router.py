"""Intelligent multi-account routing with persistent state, round-robin, and failover.

Routes requests through a pool of authenticated Genspark profiles.
Synchronizes health, cooldowns, active concurrency (in_flight), and
round-robin cursor across processes via ~/.genspark/router_state.json.

Supported Routing Strategies:
    - round-robin (default): Rotates evenly across healthy accounts, prioritizing least-busy
    - least-used: Selects healthy account with lowest total_requests and in_flight
    - failover: Sticky to default profile until unhealthy or saturated, then fails over
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
import inspect
import json
from pathlib import Path
import time
from typing import Any, Awaitable, Callable, Optional, TypeVar

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from .exceptions import (
    QuotaExhaustedError,
    RateLimitError,
    RecaptchaError,
    SessionExpiredError,
)
from .log import log
from .profiles import ProfileManager
from .session import SessionManager
from .storage import atomic_write_text, ensure_private_directory

T = TypeVar("T")

# ── Account Health States ────────────────────────────────────────────────

HEALTH_HEALTHY = "healthy"
HEALTH_COOLDOWN = "cooldown"
HEALTH_QUOTA_EXHAUSTED = "quota_exhausted"
HEALTH_EXPIRED = "expired"
HEALTH_NEEDS_LOGIN = "needs_login"

# ── Routing Strategies ───────────────────────────────────────────────────

STRATEGY_ROUND_ROBIN = "round-robin"
STRATEGY_LEAST_USED = "least-used"
STRATEGY_FAILOVER = "failover"
VALID_STRATEGIES = {STRATEGY_ROUND_ROBIN, STRATEGY_LEAST_USED, STRATEGY_FAILOVER}

# Default cooldown periods (seconds)
DEFAULT_COOLDOWN = 300       # 5 minutes after RateLimit
RECAPTCHA_COOLDOWN = 600     # 10 minutes after reCAPTCHA failure
QUOTA_COOLDOWN = 1800        # 30 minutes after daily credit / quota exhaustion
EXPIRED_COOLDOWN = 3600      # 1 hour after session expired (needs re-login)
IN_FLIGHT_STALE_SECONDS = 600.0

ROUTING_ERRORS = (
    QuotaExhaustedError,
    RateLimitError,
    SessionExpiredError,
    RecaptchaError,
)


@dataclass
class AccountStatus:
    """Track health, concurrency, and usage statistics for one account."""

    profile_name: str
    health: str = HEALTH_HEALTHY
    unhealthy_at: Optional[float] = None
    cooldown_until: Optional[float] = None
    failure_reason: str = ""
    failure_count: int = 0
    success_count: int = 0
    last_used_at: Optional[float] = None
    total_requests: int = 0
    in_flight: int = 0

    @property
    def is_available(self) -> bool:
        """Check if this account is available for requests."""
        if self.health == HEALTH_HEALTHY:
            return True
        if self.health in (HEALTH_COOLDOWN, HEALTH_QUOTA_EXHAUSTED) and self.cooldown_until:
            if time.time() >= self.cooldown_until:
                return True
        return False

    @property
    def cooldown_remaining(self) -> Optional[float]:
        """Seconds remaining in cooldown, or None if not in cooldown."""
        if self.cooldown_until:
            remaining = self.cooldown_until - time.time()
            return max(0.0, remaining) if remaining > 0 else None
        return None

    def to_persisted_dict(self) -> dict[str, Any]:
        return {
            "profile_name": self.profile_name,
            "health": self.health,
            "unhealthy_at": self.unhealthy_at,
            "cooldown_until": self.cooldown_until,
            "failure_reason": self.failure_reason,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_used_at": self.last_used_at,
            "total_requests": self.total_requests,
            "in_flight": max(0, self.in_flight),
        }

    @classmethod
    def from_persisted_dict(cls, data: dict[str, Any]) -> "AccountStatus":
        in_flight = int(data.get("in_flight", 0))
        last_used = data.get("last_used_at")
        if in_flight > 0 and last_used and (time.time() - float(last_used)) > IN_FLIGHT_STALE_SECONDS:
            in_flight = 0
        return cls(
            profile_name=str(data.get("profile_name", "default")),
            health=str(data.get("health", HEALTH_HEALTHY)),
            unhealthy_at=data.get("unhealthy_at"),
            cooldown_until=data.get("cooldown_until"),
            failure_reason=str(data.get("failure_reason", "")),
            failure_count=int(data.get("failure_count", 0)),
            success_count=int(data.get("success_count", 0)),
            last_used_at=last_used,
            total_requests=int(data.get("total_requests", 0)),
            in_flight=max(0, in_flight),
        )


class AccountRouter:
    """Routes requests through a pool of accounts with persistent state & failover."""

    def __init__(
        self,
        profiles: ProfileManager,
        strategy: Optional[str] = None,
        state_path: Optional[Path] = None,
    ):
        self.profiles = profiles
        self._explicit_strategy = strategy if strategy in VALID_STRATEGIES else None
        base_dir = getattr(profiles, "base_dir", None)
        if state_path is not None:
            self._state_path: Optional[Path] = Path(state_path)
        elif isinstance(base_dir, Path):
            ensure_private_directory(base_dir)
            self._state_path = base_dir / "router_state.json"
        else:
            self._state_path = None

        self._lock_path: Optional[Path] = (
            self._state_path.with_name(".router_state.lock")
            if self._state_path is not None
            else None
        )
        self._accounts: dict[str, AccountStatus] = {}
        self._last_used_index = -1
        with self._state_lock():
            self._load_state()
            self._refresh_pool()
            self._save_state()

    @property
    def strategy(self) -> str:
        """Current routing strategy."""
        if self._explicit_strategy:
            return self._explicit_strategy
        prof_strategy = getattr(self.profiles, "routing_strategy", STRATEGY_ROUND_ROBIN)
        return prof_strategy if prof_strategy in VALID_STRATEGIES else STRATEGY_ROUND_ROBIN

    @strategy.setter
    def strategy(self, value: str) -> None:
        if value not in VALID_STRATEGIES:
            raise ValueError(f"Invalid strategy '{value}'. Must be one of {sorted(VALID_STRATEGIES)}")
        self._explicit_strategy = value
        if hasattr(self.profiles, "update_config"):
            self.profiles.update_config(routing_strategy=value)

    @property
    def max_concurrency_per_account(self) -> int:
        return int(getattr(self.profiles, "max_concurrency", 2))

    # ── Cross-Process Locking & State Persistence ────────────────────────

    @contextmanager
    def _state_lock(self):
        if self._lock_path is None or fcntl is None:
            yield
            return
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = self._lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            fd.close()

    def _load_state(self) -> None:
        if self._state_path is None or not self._state_path.exists():
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(payload, dict):
            return
        self._last_used_index = int(payload.get("last_used_index", self._last_used_index))
        accounts_raw = payload.get("accounts", {})
        if isinstance(accounts_raw, dict):
            for name, entry in accounts_raw.items():
                if isinstance(entry, dict):
                    entry.setdefault("profile_name", name)
                    self._accounts[name] = AccountStatus.from_persisted_dict(entry)

    def _save_state(self) -> None:
        if self._state_path is None:
            return
        payload = {
            "version": 1,
            "updated_at": time.time(),
            "last_used_index": self._last_used_index,
            "accounts": {
                name: status.to_persisted_dict()
                for name, status in sorted(self._accounts.items())
            },
        }
        try:
            atomic_write_text(
                self._state_path,
                json.dumps(payload, indent=2) + "\n",
            )
        except OSError as exc:
            log.debug("Could not persist router state: %s", exc)

    def _refresh_pool(self) -> None:
        """Sync account pool with available profiles."""
        profile_list = self.profiles.list_profiles()
        existing_names = set()

        for p in profile_list:
            name = p["name"]
            existing_names.add(name)
            cookie_health = p.get("cookie_health", "fresh")
            is_logged_in = bool(p.get("is_logged_in", False))

            if name not in self._accounts:
                health = HEALTH_HEALTHY
                if not is_logged_in:
                    health = HEALTH_NEEDS_LOGIN
                elif cookie_health == "expired":
                    health = HEALTH_EXPIRED
                self._accounts[name] = AccountStatus(
                    profile_name=name,
                    health=health,
                )
            else:
                status = self._accounts[name]
                if not is_logged_in:
                    status.health = HEALTH_NEEDS_LOGIN
                elif cookie_health == "expired":
                    status.health = HEALTH_EXPIRED
                elif status.health in (HEALTH_NEEDS_LOGIN, HEALTH_EXPIRED) and is_logged_in:
                    status.health = HEALTH_HEALTHY
                    status.failure_reason = ""

        for name in list(self._accounts):
            if name not in existing_names:
                del self._accounts[name]

    # ── Session Selection ────────────────────────────────────────────────

    def get_session(
        self,
        preferred: Optional[str] = None,
        exclude: Optional[set[str]] = None,
    ) -> SessionManager:
        """Get the best available session according to the active routing strategy."""
        with self._state_lock():
            self._load_state()
            self._refresh_pool()

            excluded = exclude or set()

            # 1. Explicit preferred profile takes priority if available
            if preferred and preferred not in excluded and self._is_available(preferred):
                return self._use(preferred)

            # 2. Gather all available accounts
            ordered_names = list(self._accounts.keys())
            available = [
                name for name in ordered_names
                if name not in excluded and self._accounts[name].is_available
            ]

            if not available:
                self._save_state()
                self._raise_no_accounts_error()

            active_strategy = self.strategy

            # 3a. Failover (sticky) strategy: prefer default profile first
            if active_strategy == STRATEGY_FAILOVER:
                default = self.profiles.default_profile
                if default in available:
                    default_in_flight = self._accounts[default].in_flight
                    if default_in_flight < self.max_concurrency_per_account or len(available) == 1:
                        return self._use(default)

            # 3b. Least-used strategy: lowest (in_flight, total_requests, last_used_at)
            if active_strategy == STRATEGY_LEAST_USED:
                chosen = min(
                    available,
                    key=lambda n: (
                        self._accounts[n].in_flight,
                        self._accounts[n].total_requests,
                        self._accounts[n].last_used_at or 0.0,
                    ),
                )
                return self._use(chosen)

            # 3c. Round-robin + least-busy strategy (Default)
            min_in_flight = min(self._accounts[n].in_flight for n in available)
            least_busy = [
                n for n in available
                if self._accounts[n].in_flight == min_in_flight
            ]
            self._last_used_index = (self._last_used_index + 1) % len(least_busy)
            chosen = least_busy[self._last_used_index]
            return self._use(chosen)

    def _raise_no_accounts_error(self) -> None:
        cooldown_accounts = [
            (name, status.cooldown_remaining, status.failure_reason or status.health)
            for name, status in self._accounts.items()
            if status.health in (HEALTH_COOLDOWN, HEALTH_QUOTA_EXHAUSTED) and status.cooldown_remaining
        ]
        if cooldown_accounts:
            soonest = min(cooldown_accounts, key=lambda x: x[1])
            details = ", ".join(
                f"{name}: {int(rem)}s ({reason})"
                for name, rem, reason in cooldown_accounts
            )
            raise RuntimeError(
                f"All accounts are in cooldown. "
                f"'{soonest[0]}' will be available in {int(soonest[1])}s [{details}]. "
                f"Reset with 'gsk pool reset' or add another account: genspark auth add <name>"
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

    def _is_available(self, name: str) -> bool:
        """Check if a named account is available."""
        status = self._accounts.get(name)
        if not status:
            return False
        return status.is_available

    def _use(self, name: str) -> SessionManager:
        """Select an account for use, update tracking, and persist."""
        status = self._accounts[name]
        status.last_used_at = time.time()
        status.total_requests += 1
        status.in_flight = max(0, status.in_flight) + 1

        if status.health in (HEALTH_COOLDOWN, HEALTH_QUOTA_EXHAUSTED):
            log.info(
                "Cooldown expired for '%s' — retrying (half-open)",
                name,
                extra={"event": "account_halfopen", "profile": name},
            )

        self._save_state()
        session = self.profiles.get_session(name)
        log.debug(
            "Using account '%s' (total requests: %d, in_flight: %d)",
            name,
            status.total_requests,
            status.in_flight,
            extra={"event": "account_selected", "profile": name},
        )
        return session

    def release_session(self, name: str) -> None:
        """Decrement active in-flight request counter for an account."""
        with self._state_lock():
            self._load_state()
            status = self._accounts.get(name)
            if status is not None:
                status.in_flight = max(0, status.in_flight - 1)
                self._save_state()

    # ── Health Management ────────────────────────────────────────────────

    def mark_success(self, name: str) -> None:
        """Mark an account as healthy after successful request."""
        with self._state_lock():
            self._load_state()
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
            status.in_flight = max(0, status.in_flight - 1)
            self._save_state()

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
        """Mark an account as unhealthy with a cooldown period."""
        with self._state_lock():
            self._load_state()
            status = self._accounts.get(name)
            if not status:
                return

            reason_lower = reason.lower()
            is_quota = any(k in reason_lower for k in ("quota", "credit", "exhausted", "402"))

            if cooldown is None:
                default_cd = float(getattr(self.profiles, "default_cooldown_s", DEFAULT_COOLDOWN))
                if is_quota:
                    cooldown = QUOTA_COOLDOWN
                elif "rate" in reason_lower:
                    cooldown = default_cd
                elif "recaptcha" in reason_lower:
                    cooldown = RECAPTCHA_COOLDOWN
                elif "expired" in reason_lower or "auth" in reason_lower or "session" in reason_lower:
                    cooldown = EXPIRED_COOLDOWN
                else:
                    cooldown = default_cd

            status.health = HEALTH_QUOTA_EXHAUSTED if is_quota else HEALTH_COOLDOWN
            status.unhealthy_at = time.time()
            status.cooldown_until = time.time() + float(cooldown)
            status.failure_reason = reason
            status.failure_count += 1
            status.in_flight = max(0, status.in_flight - 1)
            self._save_state()

            log.warning(
                "Account '%s' marked %s: %s (cooldown %ds, failures: %d)",
                name,
                status.health,
                reason,
                int(cooldown),
                status.failure_count,
                extra={
                    "event": "account_unhealthy",
                    "profile": name,
                    "reason": reason,
                    "cooldown": cooldown,
                },
            )

    def mark_needs_login(self, name: str) -> None:
        """Mark an account as needing re-authentication."""
        with self._state_lock():
            self._load_state()
            status = self._accounts.get(name)
            if not status:
                return
            status.health = HEALTH_NEEDS_LOGIN
            status.failure_reason = "needs re-login"
            status.in_flight = 0
            self._save_state()
            log.warning(
                "Account '%s' needs re-login",
                name,
                extra={"event": "account_needs_login", "profile": name},
            )

    def reset_cooldowns(self, name: Optional[str] = None) -> int:
        """Clear cooldown/quota_exhausted state for one or all accounts."""
        with self._state_lock():
            self._load_state()
            self._refresh_pool()
            reset_count = 0
            targets = [name] if name else list(self._accounts.keys())
            for target in targets:
                status = self._accounts.get(target)
                if not status:
                    continue
                if status.health in (HEALTH_COOLDOWN, HEALTH_QUOTA_EXHAUSTED) or status.in_flight > 0:
                    status.health = HEALTH_HEALTHY
                    status.cooldown_until = None
                    status.unhealthy_at = None
                    status.failure_reason = ""
                    status.in_flight = 0
                    reset_count += 1
            self._save_state()
            return reset_count

    # ── Universal Failover Execution ─────────────────────────────────────

    async def execute_with_failover(
        self,
        operation: Callable[[SessionManager], Awaitable[T] | T],
        preferred: Optional[str] = None,
        on_failover: Optional[Callable[[str, str, Exception], None]] = None,
    ) -> T:
        """Execute an async (or sync) operation with automatic multi-account failover.

        Strictly preserves the caller's model and parameters across retries.
        """
        statuses = self.get_status()
        max_attempts = max(1, len(statuses))
        tried_profiles: set[str] = set()
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                session = self.get_session(
                    preferred=preferred if attempt == 0 else None,
                    exclude=tried_profiles if attempt > 0 else None,
                )
            except RuntimeError:
                if last_error is not None:
                    raise last_error
                raise

            profile_name = getattr(session, "profile_name", "default")
            tried_profiles.add(profile_name)

            try:
                outcome = operation(session)
                result = await outcome if inspect.isawaitable(outcome) else outcome
                self.mark_success(profile_name)
                return result
            except ROUTING_ERRORS as exc:
                last_error = exc
                reason = f"{type(exc).__name__}: {exc}".splitlines()[0][:120]
                self.mark_unhealthy(profile_name, reason=reason)
                if on_failover is not None:
                    try:
                        on_failover(profile_name, reason, exc)
                    except Exception:
                        pass
            except Exception:
                self.release_session(profile_name)
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("No Genspark browser profiles are available")

    def run_with_failover(
        self,
        operation: Callable[[SessionManager], Awaitable[T] | T],
        preferred: Optional[str] = None,
        on_failover: Optional[Callable[[str, str, Exception], None]] = None,
    ) -> T:
        """Synchronous wrapper for execute_with_failover."""
        return asyncio.run(
            self.execute_with_failover(
                operation,
                preferred=preferred,
                on_failover=on_failover,
            )
        )

    # ── Status ───────────────────────────────────────────────────────────

    def get_status(self) -> list[dict[str, Any]]:
        """Get status of all accounts in the pool."""
        with self._state_lock():
            self._load_state()
            self._refresh_pool()
            self._save_state()
            statuses = []
            for name, status in sorted(self._accounts.items()):
                entry: dict[str, Any] = {
                    "name": name,
                    "health": status.health,
                    "is_available": status.is_available,
                    "is_default": name == self.profiles.default_profile,
                    "success_count": status.success_count,
                    "failure_count": status.failure_count,
                    "total_requests": status.total_requests,
                    "in_flight": status.in_flight,
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
        with self._state_lock():
            self._load_state()
            self._refresh_pool()
            return len(self._accounts)

    @property
    def available_count(self) -> int:
        """Number of currently available accounts."""
        with self._state_lock():
            self._load_state()
            self._refresh_pool()
            return sum(1 for s in self._accounts.values() if s.is_available)

    def __repr__(self) -> str:
        return (
            f"<AccountRouter pool={self.pool_size} "
            f"available={self.available_count} "
            f"strategy='{self.strategy}' "
            f"default='{self.profiles.default_profile}'>"
        )
