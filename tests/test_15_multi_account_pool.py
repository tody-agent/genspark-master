import json
import httpx
import pytest

from genspark_cli.account_router import (
    AccountRouter,
    HEALTH_COOLDOWN,
    HEALTH_HEALTHY,
    HEALTH_QUOTA_EXHAUSTED,
    STRATEGY_FAILOVER,
    STRATEGY_LEAST_USED,
    STRATEGY_ROUND_ROBIN,
)
from genspark_cli.client import GensparkClient
from genspark_cli.exceptions import (
    QuotaExhaustedError,
    RateLimitError,
    RecaptchaError,
    SessionExpiredError,
)
from genspark_cli.profiles import ProfileManager
from genspark_cli.session import SessionManager


def _create_logged_in_profile(pm: ProfileManager, name: str) -> SessionManager:
    if name == "default":
        session = pm.get_session("default")
    else:
        session = pm.add_profile(name)
    session.save_storage_state(
        {"cookies": [{"name": "ai_session", "value": f"cookie-{name}"}]}
    )
    session.save_recaptcha_token(f"token-{name}")
    return session


def test_profile_manager_extended_config_and_import(tmp_path):
    pm = ProfileManager(str(tmp_path))
    assert pm.routing_strategy == STRATEGY_ROUND_ROBIN
    assert pm.max_concurrency == 2

    pm.update_config(
        routing_strategy=STRATEGY_LEAST_USED,
        max_concurrency_per_account=4,
        default_model="gpt-6-sol",
        default_image_model="flux-2-pro",
    )

    pm2 = ProfileManager(str(tmp_path))
    assert pm2.routing_strategy == STRATEGY_LEAST_USED
    assert pm2.max_concurrency == 4
    assert pm2.default_model == "gpt-6-sol"
    assert pm2.default_image_model == "flux-2-pro"

    imported = pm2.import_profile(
        "acc-imported",
        storage_state={"cookies": [{"name": "ai_session", "value": "imported-cookie"}]},
        recaptcha_token="imported-token",
    )
    assert imported.is_logged_in
    assert imported.get_recaptcha_token() == "imported-token"


def test_cross_process_round_robin_persists_across_router_instances(tmp_path):
    pm = ProfileManager(str(tmp_path))
    _create_logged_in_profile(pm, "default")
    _create_logged_in_profile(pm, "acc2")
    _create_logged_in_profile(pm, "acc3")

    # Separate AccountRouter instances simulate separate CLI / MCP processes
    r1 = AccountRouter(ProfileManager(str(tmp_path)), strategy=STRATEGY_ROUND_ROBIN)
    s1 = r1.get_session()
    r1.release_session(s1.profile_name)

    r2 = AccountRouter(ProfileManager(str(tmp_path)), strategy=STRATEGY_ROUND_ROBIN)
    s2 = r2.get_session()
    r2.release_session(s2.profile_name)

    r3 = AccountRouter(ProfileManager(str(tmp_path)), strategy=STRATEGY_ROUND_ROBIN)
    s3 = r3.get_session()
    r3.release_session(s3.profile_name)

    r4 = AccountRouter(ProfileManager(str(tmp_path)), strategy=STRATEGY_ROUND_ROBIN)
    s4 = r4.get_session()
    r4.release_session(s4.profile_name)

    selected = [s1.profile_name, s2.profile_name, s3.profile_name]
    assert len(set(selected)) == 3
    assert s4.profile_name == s1.profile_name


def test_round_robin_prefers_least_busy_when_in_flight(tmp_path):
    pm = ProfileManager(str(tmp_path))
    _create_logged_in_profile(pm, "acc1")
    _create_logged_in_profile(pm, "acc2")

    router = AccountRouter(pm, strategy=STRATEGY_ROUND_ROBIN)
    # Acquire two concurrent sessions without releasing the first
    first = router.get_session()
    second = router.get_session()
    assert first.profile_name != second.profile_name

    router.release_session(first.profile_name)
    router.release_session(second.profile_name)


def test_least_used_and_failover_strategies(tmp_path):
    pm = ProfileManager(str(tmp_path))
    _create_logged_in_profile(pm, "default")
    _create_logged_in_profile(pm, "backup")

    # Failover (sticky) always picks default while healthy
    sticky_router = AccountRouter(pm, strategy=STRATEGY_FAILOVER)
    a1 = sticky_router.get_session()
    sticky_router.release_session(a1.profile_name)
    a2 = sticky_router.get_session()
    sticky_router.release_session(a2.profile_name)
    assert a1.profile_name == "default"
    assert a2.profile_name == "default"

    # Least-used picks backup since default now has 2 requests and backup has 0
    lu_router = AccountRouter(pm, strategy=STRATEGY_LEAST_USED)
    a3 = lu_router.get_session()
    lu_router.release_session(a3.profile_name)
    assert a3.profile_name == "backup"


@pytest.mark.asyncio
async def test_execute_with_failover_rotates_on_quota_and_rate_limit(tmp_path):
    pm = ProfileManager(str(tmp_path))
    _create_logged_in_profile(pm, "default")
    _create_logged_in_profile(pm, "acc2")
    _create_logged_in_profile(pm, "acc3")

    router = AccountRouter(pm, strategy=STRATEGY_ROUND_ROBIN)
    attempted = []
    failover_events = []

    async def op(session: SessionManager):
        attempted.append(session.profile_name)
        if len(attempted) == 1:
            raise QuotaExhaustedError("Daily credits exhausted")
        if len(attempted) == 2:
            raise RateLimitError("Too many requests")
        return {"ok": True, "profile": session.profile_name}

    result = await router.execute_with_failover(
        op,
        on_failover=lambda failed, reason, exc: failover_events.append((failed, reason)),
    )
    assert result["ok"] is True
    assert len(attempted) == 3
    assert len(set(attempted)) == 3
    assert len(failover_events) == 2

    statuses = {s["name"]: s for s in router.get_status()}
    assert statuses[attempted[0]]["health"] in (HEALTH_QUOTA_EXHAUSTED, HEALTH_COOLDOWN)
    assert statuses[attempted[1]]["health"] == HEALTH_COOLDOWN
    assert statuses[attempted[2]]["health"] == HEALTH_HEALTHY

    # Reset cooldowns restores all accounts
    reset_count = router.reset_cooldowns()
    assert reset_count == 2
    assert router.available_count == 3


@pytest.mark.asyncio
async def test_client_detects_http_402_and_sse_quota_exhausted(tmp_path):
    session = SessionManager(str(tmp_path))
    session.save_storage_state({"cookies": [{"name": "ai_session", "value": "c"}]})
    session.save_recaptcha_token("tok")

    async def no_refresh(_):
        return None

    # 1. HTTP 402 raises QuotaExhaustedError
    transport_402 = httpx.MockTransport(lambda req: httpx.Response(402))
    async with GensparkClient(session, http_transport=transport_402, refresh_callback=no_refresh) as client:
        with pytest.raises(QuotaExhaustedError):
            await client.chat("hello")

    # 2. SSE stream containing quota/credit error raises QuotaExhaustedError
    sse_quota = "\n".join([
        'data: {"type":"error","message":"Insufficient credits for this model. Daily quota exceeded."}',
        "",
    ])
    transport_sse_err = httpx.MockTransport(lambda req: httpx.Response(200, text=sse_quota))
    async with GensparkClient(session, http_transport=transport_sse_err, refresh_callback=no_refresh) as client:
        with pytest.raises(QuotaExhaustedError, match="Insufficient credits"):
            await client.chat("hello")
