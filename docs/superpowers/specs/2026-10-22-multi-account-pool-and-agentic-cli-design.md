# Genspark Master v0.6 — Multi-Account Pool, Parallel Batch Engine & Agentic CLI UX Design Spec

**Date:** 2026-10-22  
**Status:** Approved  
**Author:** Antigravity & User  
**Target Package:** `genspark-cli` (`/Volumes/Builder/Skills/genspark-master`)

---

## 1. Problem Statement & Goals

The existing `genspark-cli` (`v0.5.0`) supports storing multiple browser profiles under `~/.genspark/profiles/<name>/` and includes an initial `AccountRouter`. However, five architectural limitations prevent it from running large-scale multi-threaded workloads across multiple accounts smoothly:

1. **In-Memory Ephemeral Router State**: `AccountRouter` stores health, cooldowns, and round-robin indices in memory only, and `get_session()` always selects `default_profile` first when healthy. Separate CLI calls, subagents, or parallel tasks all hammer the `default` account instead of distributing load.
2. **Missing Auto-Failover in Core CLI Commands**: `genspark chat ask`, `genspark run`, and `genspark image generate` only attempt a single profile and exit on `RateLimitError`, `SessionExpiredError`, or `RecaptchaError` instead of failing over across the pool.
3. **Undetected Quota / Credit Exhaustion**: When an account exhausts its daily credits or model quota (HTTP `402` or SSE error payload), the parser and client do not raise a typed routing error (`QuotaExhaustedError`), preventing automatic rotation to the next account.
4. **No Multi-Account Parallel Batch Execution**: Large projects with dozens of prompts, files, or image generations must wait sequentially instead of dispatching concurrently across $M$ accounts.
5. **High-Friction CLI UX**: Typing `genspark chat ask "..."` is verbose compared to **Claude Code** (`claude`) or **Hermes Agent CLI** (`hermes`), and configuring models, routing strategies, or inspecting/testing the account pool lacks a streamlined interactive experience.

### Core Goals
- **Cross-Process Persistent Account Pool (`~/.genspark/router_state.json` + File Lock)**: Synchronize account health, cooldowns, in-flight concurrency, request counters, and round-robin cursor across all CLI processes, MCP tool calls, and the OpenAI proxy server.
- **Smart Round-Robin + Least-Busy Auto-Routing**: Distribute requests evenly across all healthy accounts, prioritizing accounts with the fewest active in-flight requests, and automatically failing over when an account hits rate limits, reCAPTCHA challenges, expired cookies, or credit exhaustion.
- **Strict Model Integrity on Exhaustion**: Never silently downgrade the user's selected model when all accounts are exhausted; instead, stop and report a detailed per-account status and cooldown breakdown.
- **Parallel Multi-Account Batch Engine (`gsk batch` & MCP `batch_chat` / `batch_generate_images`)**: Execute $N$ chat or image tasks concurrently across $M$ accounts with per-account concurrency semaphores and transparent task retry on healthy accounts.
- **Claude Code / Hermes Agent CLI UX**:
  - `gsk` (no args in TTY) launches the interactive Studio REPL with live HUD status bar, readline history, and tab completion.
  - `gsk "prompt"` and `gsk -i "prompt"` execute chat/image tasks immediately with full pool failover.
  - `gsk pool` manages, pings, imports, and inspects all accounts.
  - `gsk config` provides both an interactive configuration wizard and scriptable `show`/`set` commands.
  - 100% backward compatibility with all existing CLI commands, MCP tools, and test contracts.

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                  User / AI Agents (Claude Code, AGY, Codex)                │
└───────────┬──────────────────────────────┬─────────────────────────────────┘
            │ CLI (`gsk`, `gsk batch`,     │ MCP (`chat`, `batch_chat`,
            │      `gsk pool`, `gsk config`)│      `generate_image`, `batch_generate_images`)
            ▼                              ▼
┌────────────────────────────────────────────────────────────────────────────┐
│               MultiAccountBatchExecutor & AutoFailoverRunner               │
│   • Per-account concurrency semaphores (max_concurrency_per_account)       │
│   • Automatic retry across healthy profiles on Routing Errors              │
│   • Strict model integrity (no silent model downgrade)                     │
└───────────────────────────────────┬────────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│             Persistent AccountRouter (~/.genspark/router_state.json)       │
│   • POSIX fcntl.flock atomic cross-process state synchronization           │
│   • Strategies: round-robin (default + least-busy), least-used, failover   │
│   • Circuit Breaker: healthy -> cooldown / quota_exhausted -> half-open    │
└───────────────────────────────────┬────────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                 ProfileManager (~/.genspark/profiles/*)                    │
│   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐                │
│   │   default/    │   │    acc-02/    │   │    acc-03/    │ ...            │
│   │ cookies+token │   │ cookies+token │   │ cookies+token │                │
│   └───────────────┘   └───────────────┘   └───────────────┘                │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Specifications

### 3.1 Exceptions & Quota Detection (`exceptions.py`, `parser.py`, `client.py`, `image_client.py`)
- **`QuotaExhaustedError(RateLimitError)`**:
  - Raised when HTTP status is `402` or when SSE stream contains an explicit error event/message indicating exhausted credits or quota (`insufficient credit`, `out of credit`, `credit limit`, `quota exceeded`, `daily limit reached`, `upgrade your plan`).
  - Subclasses `RateLimitError` so existing `except (RateLimitError, SessionExpiredError, RecaptchaError)` handlers catch it automatically.
  - Default cooldown: `QUOTA_COOLDOWN = 1800` seconds (30 minutes).

### 3.2 Extended Configuration (`profiles.py`)
`ProfileManager` stores global user configuration in `~/.genspark/config.json` (`0o600`):
- `default_profile`: `str` (default `"default"`)
- `default_model`: `str` (default `"claude-opus-5.5"`)
- `default_image_model`: `str` (default `"nano-banana-2"`)
- `routing_strategy`: `"round-robin" | "least-used" | "failover"` (default `"round-robin"`)
- `max_concurrency_per_account`: `int` (default `2`)
- `default_cooldown_s`: `int` (default `300`)

### 3.3 Persistent Cross-Process `AccountRouter` (`account_router.py`)
- **State Persistence**:
  - When `profiles` provides a `base_dir`, `AccountRouter` persists `_accounts` and `_last_used_index` to `<base_dir>/router_state.json` (`0o600`), guarded by `<base_dir>/.router_state.lock` using `fcntl.flock`.
  - Tracks per-account fields: `health` (`healthy`, `cooldown`, `quota_exhausted`, `expired`, `needs_login`), `unhealthy_at`, `cooldown_until`, `failure_reason`, `failure_count`, `success_count`, `last_used_at`, `total_requests`, `in_flight`.
- **Selection Logic (`get_session(preferred=None)`)**:
  1. If `preferred` is explicitly provided and available, select `preferred`.
  2. Filter available accounts (`status.is_available`).
  3. Apply active strategy:
     - `round-robin` (default): Rotate sequentially via `_last_used_index = (_last_used_index + 1) % len(available)`, breaking ties in favor of accounts with lower `in_flight` count when concurrent requests are active.
     - `least-used`: Select available account with minimum `(in_flight, total_requests, last_used_at)`.
     - `failover`: Select `default_profile` if available and `in_flight < max_concurrency`; otherwise pick next available account.
  4. If no accounts are available:
     - Raise `RuntimeError` with `"All accounts are in cooldown..."` (when cooldown/quota accounts exist) and a detailed per-account breakdown of health, reason, and remaining seconds.
- **Failover Execution Helpers**:
  - `async def execute_with_failover(self, operation, preferred=None, on_failover=None)`
  - Attempts `operation(session)` up to `max(1, available_count)` times across distinct healthy accounts.
  - On `(RateLimitError, QuotaExhaustedError, SessionExpiredError, RecaptchaError)`, marks the failing account unhealthy with reason-appropriate cooldown and immediately retries on the next healthy account.

### 3.4 Parallel Multi-Account Batch Engine (`batch.py`)
- **`BatchTask` & `BatchResult` dataclasses**:
  - `BatchTask(id: str, prompt: str, model: str | None = None, system_prompt: str | None = None, metadata: dict = ...)`
  - `BatchResult(id: str, prompt: str, status: "ok" | "error", content: str = "", urls: list[str] = [], local_paths: list[str] = [], profile: str = "", model: str = "", elapsed_s: float = 0.0, error: str = "", attempts: int = 1)`
- **`MultiAccountBatchExecutor`**:
  - Runs `execute_chat_batch(tasks, concurrency=...)` and `execute_image_batch(tasks, concurrency=..., style=..., aspect_ratio=..., image_size=..., output_dir=..., download=...)`.
  - Uses per-account `asyncio.Semaphore(max_concurrency_per_account)` plus global `asyncio.Semaphore(concurrency)`.
  - Automatically re-routes failed tasks to another healthy account on routing errors without aborting the batch.

### 3.5 Agentic CLI & Interactive Studio (`cli.py`, `interactive.py`, `config_ui.py`)
- **Top-Level `GensparkGroup(click.Group)`**:
  - Supports running `gsk` with no arguments $\rightarrow$ launches Interactive Studio REPL (when stdin/stdout is a TTY; otherwise prints help).
  - Supports shorthand `gsk "prompt"` or `gsk -i "image prompt"` by forwarding unrecognized positional arguments to `run` / `image generate`.
  - Preserves all standard subcommands (`auth`, `chat`, `run`, `pool`, `batch`, `config`, `models`, `session`, `server`, `mcp`, `image`, `integrate`, `doctor`, `capabilities`).
- **`gsk pool` Command Group**:
  - `gsk pool status [--json]` (default when running `gsk pool`)
  - `gsk pool add <names>...`
  - `gsk pool strategy <round-robin|least-used|failover>`
  - `gsk pool reset`
  - `gsk pool ping [--model glm-5.3-flash]`
  - `gsk pool import <name> <storage_state_file> [--token <token>]`
- **`gsk batch` Command**:
  - `gsk batch [PROMPTS]... [--input-file / -f FILE] [--output / -o PATH] [--model / -m MODEL] [--concurrency / -c INT] [--image] [--style STYLE] [--ratio RATIO] [--size SIZE] [--json]`
- **`gsk config` Command Group**:
  - `gsk config` (interactive wizard in TTY, or shows current config)
  - `gsk config show [--json]`
  - `gsk config set <key> <value>`
  - `gsk config reset`
- **Upgraded Interactive REPL (`interactive.py`)**:
  - Rich HUD header displaying Model, Multiplier, Account Pool (`available/total`), Strategy, and Session ID.
  - Readline command history (`~/.genspark/history`) and slash-command tab completion.
  - Slash commands: `/pool`, `/strategy`, `/config`, `/reset`, `/image`, `/batch`, `/model`, `/models`, `/session`, `/compact`, `/context`, `/history`, `/status`, `/accounts`, `/clear`, `/raw`, `/help`, `/quit`.
  - Automatic per-turn account routing via `AccountRouter` (`round-robin` / `least-used` / `failover`) with transparent mid-turn failover.

---

## 4. Testing & Verification Strategy
- Fix pre-existing `test_06_image_models.py::TestImageModels::test_resolve_image_model_unknown` regression.
- Verify all 14 existing test modules (`test_01` to `test_14`) pass 100%.
- Add `tests/test_15_multi_account_pool.py` testing persistent state, cross-instance round-robin, least-busy selection, `QuotaExhaustedError` detection, and `execute_with_failover`.
- Add `tests/test_16_batch_executor.py` testing concurrent multi-account chat and image batch execution, per-account failover during batch runs, and MCP `batch_chat` / `batch_generate_images` tools.
- Add `tests/test_17_agentic_cli_ux.py` testing `gsk "prompt"` shorthand, `gsk pool status/strategy/reset/import`, `gsk config show/set`, and `gsk batch --json`.
- Run `./scripts/test_gate.sh` to verify pytest suite, bytecode compilation, and Codex plugin validation.
