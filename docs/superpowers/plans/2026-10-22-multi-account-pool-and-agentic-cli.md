# Genspark Multi-Account Pool, Parallel Batch Engine & Agentic CLI Implementation Plan

> **For agentic workers:** Contract-driven vertical slices implementing `docs/superpowers/specs/2026-10-22-multi-account-pool-and-agentic-cli-design.md`.

**Goal:** Upgrade `genspark-cli` (`genspark` / `gsk`) and `genspark-mcp` with a cross-process persistent multi-account pool, smart `round-robin` + `least-busy` routing, automatic failover across all CLI/MCP/Server commands, a concurrent multi-account batch engine (`gsk batch`), and a Claude Code / Hermes Agent style CLI & REPL UX.

**Architecture:** Persistent `AccountRouter` backed by `~/.genspark/router_state.json` with `fcntl.flock` synchronization; `MultiAccountBatchExecutor` for async concurrent execution across accounts; custom `GensparkGroup` Click command router supporting zero-friction `gsk`, `gsk "prompt"`, `gsk pool`, `gsk batch`, and `gsk config`.

**Tech Stack:** Python 3.10+, `click`, `httpx`, `aiohttp`, `rich`, `pydantic`, `pytest`, `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-10-22-multi-account-pool-and-agentic-cli-design.md`

## Global Constraints

- Never introduce API-key authentication; all requests use browser cookies + reCAPTCHA tokens.
- Never write placeholder secrets (`sk-...` >= 20 chars or `api_key = "..."`) in `genspark_cli/*.py` (enforced by `tests/test_05_security_scan.py`).
- Preserve the 3 canonical skill folders (`gen-setup`, `gen-chat`, `gen-imagegen`) with only `name` and `description` in YAML frontmatter (enforced by `tests/test_13_installation.py`).
- Strictly preserve user-selected model when accounts are exhausted (no silent model downgrade); report detailed cooldown status per account.
- All state and config files in `~/.genspark/` must use `0o600` permissions via `atomic_write_text`.

## Review Focus

- Cross-process round-robin rotation: consecutive `AccountRouter(pm).get_session()` calls across separate router instances must rotate through all healthy profiles instead of sticking to `default`.
- SSE inline quota error detection: when HTTP 200 SSE contains a quota/credit error event, `GensparkClient` must raise `QuotaExhaustedError` so `AccountRouter` marks the account unhealthy and fails over.
- Strict model integrity: `execute_with_failover` must never alter `model` on failover and must raise a detailed `RuntimeError` when all accounts are in cooldown.
- Image model validation: `resolve_image_model("nonexistent-model-xyz")` must raise `ValueError("Unknown image model...")` as required by `tests/test_06_image_models.py`.
- Shorthand CLI safety: `gsk capabilities --json` and `gsk doctor --json` must emit clean machine-readable JSON on stdout with zero extra banner text.

---

### Slice 1: Quota Detection, Image Model Fix & Extended Profile Config

**Files:**
- Modify: `genspark_cli/exceptions.py`
- Modify: `genspark_cli/image_models.py`
- Modify: `genspark_cli/parser.py`
- Modify: `genspark_cli/client.py`
- Modify: `genspark_cli/profiles.py`
- Test: `tests/test_06_image_models.py`, `tests/test_15_multi_account_pool.py`

**Interfaces:**
- Consumes: `SessionManager`, `atomic_write_text`
- Produces:
  - `QuotaExhaustedError(RateLimitError)` in `genspark_cli.exceptions`
  - `ProfileManager.routing_strategy: str`, `ProfileManager.max_concurrency: int`, `ProfileManager.default_model: str`, `ProfileManager.default_image_model: str`, `ProfileManager.get_config() -> dict`, `ProfileManager.update_config(**kwargs) -> dict`
  - `ProfileManager.import_profile(name: str, storage_state: dict, recaptcha_token: str | None = None) -> SessionManager`
- Verify Cmd: `.venv/bin/python -m pytest tests/test_06_image_models.py tests/test_08_session_security.py -q`

---

### Slice 2: Persistent Cross-Process `AccountRouter` & Universal Auto-Failover

**Files:**
- Modify: `genspark_cli/account_router.py`
- Modify: `genspark_cli/server.py`
- Test: `tests/test_03_business_logic.py`, `tests/test_15_multi_account_pool.py`

**Interfaces:**
- Consumes: `ProfileManager`, `SessionManager`, `QuotaExhaustedError`, `RateLimitError`, `SessionExpiredError`, `RecaptchaError`
- Produces:
  - `AccountRouter(profiles, strategy: str | None = None, state_path: Path | None = None)`
  - `AccountRouter.get_session(preferred: str | None = None) -> SessionManager`
  - `AccountRouter.release_session(name: str) -> None`
  - `AccountRouter.reset_cooldowns(name: str | None = None) -> int`
  - `AccountRouter.execute_with_failover(operation: Callable[[SessionManager], Awaitable[T]], preferred: str | None = None, on_failover: Callable[[str, str, Exception], None] | None = None) -> T`
  - `AccountRouter.run_with_failover(operation: Callable[[SessionManager], T], preferred: str | None = None, on_failover: Callable[[str, str, Exception], None] | None = None) -> T`
- Verify Cmd: `.venv/bin/python -m pytest tests/test_03_business_logic.py tests/test_15_multi_account_pool.py -q`

---

### Slice 3: Multi-Account Parallel Batch Engine & MCP Batch Tools

**Files:**
- Create: `genspark_cli/batch.py`
- Modify: `genspark_cli/mcp.py`
- Test: `tests/test_11_mcp.py`, `tests/test_16_batch_executor.py`

**Interfaces:**
- Consumes: `AccountRouter`, `GensparkClient`, `GensparkImageClient`
- Produces:
  - `BatchTask`, `BatchResult`, `MultiAccountBatchExecutor` in `genspark_cli.batch`
  - `batch_chat(...)`, `batch_generate_images(...)`, `configure_pool(...)` in `genspark_cli.mcp`
- Verify Cmd: `.venv/bin/python -m pytest tests/test_11_mcp.py tests/test_16_batch_executor.py -q`

---

### Slice 4: Claude Code / Hermes Agent CLI UX (`gsk`, `pool`, `batch`, `config`, Interactive REPL)

**Files:**
- Modify: `genspark_cli/cli.py`
- Modify: `genspark_cli/interactive.py`
- Modify: `skills/gen-setup/SKILL.md`, `skills/gen-chat/SKILL.md`, `skills/gen-imagegen/SKILL.md`, `rules/AGENTS.md`, `README.md`
- Test: `tests/test_12_cli_contracts.py`, `tests/test_13_installation.py`, `tests/test_14_plugin_archive.py`, `tests/test_17_agentic_cli_ux.py`

**Interfaces:**
- Consumes: `AccountRouter`, `MultiAccountBatchExecutor`, `ProfileManager`
- Produces:
  - `GensparkGroup` in `genspark_cli.cli` supporting `gsk`, `gsk "prompt"`, `gsk -i "prompt"`, `gsk pool`, `gsk batch`, `gsk config`
  - Upgraded `interactive_chat` in `genspark_cli.interactive` with HUD status bar, readline autocomplete, `/pool`, `/strategy`, `/config`, `/reset`, `/image`, `/batch`
- Verify Cmd: `./scripts/test_gate.sh`
