# 🏛️ Genspark Master AI Suite — Technical Architecture

This document provides a comprehensive technical overview of the Genspark Master AI Suite architecture, its multi-account routing engine, parallel batch system, cross-agent plugin standard, and security boundary model.

---

## 1. System Overview

```
                               ┌──────────────────────────────────────────────────┐
                               │           Client Entrypoints & Agents            │
                               │  ┌────────────┐  ┌─────────────┐  ┌───────────┐  │
                               │  │  gsk CLI   │  │ Claude Code │  │  AGY /    │  │
                               │  │ (Terminal) │  │   Plugin    │  │   Codex   │  │
                               │  └─────┬──────┘  └──────┬──────┘  └─────┬─────┘  │
                               └────────┼────────────────┼───────────────┼────────┘
                                        │                │               │
                                        ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Genspark Master Runtime Engine                         │
│                                                                                 │
│   ┌─────────────────────┐   ┌───────────────────────────┐   ┌───────────────┐   │
│   │ Interactive Menu &  │   │     MCP Stdio Server      │   │ OpenAI Proxy  │   │
│   │ Onboarding (menu.py)│   │  (9 tools via mcp.py)     │   │   (server.py) │   │
│   └──────────┬──────────┘   └─────────────┬─────────────┘   └───────┬───────┘   │
│              │                            │                         │           │
│              └──────────────────┐         │         ┌───────────────┘           │
│                                 ▼         ▼         ▼                           │
│                     ┌───────────────────────────────────────────────┐           │
│                     │        AccountRouter (account_router.py)      │           │
│                     │  • Persistent lock: fcntl.flock (.lock)       │           │
│                     │  • Cross-process state: router_state.json     │           │
│                     │  • In-flight tracker & least-busy load balancer│          │
│                     └───────────────────────┬───────────────────────┘           │
│                                             │                                   │
│                        ┌────────────────────┴────────────────────┐              │
│                        ▼                                         ▼              │
│          ┌───────────────────────────┐             ┌──────────────────────────┐ │
│          │  Direct Chat HTTP Client  │             │   Image Generation API   │ │
│          │   (SSE Chunk Interceptor) │             │    (Async Downloader)    │ │
│          └─────────────┬─────────────┘             └────────────┬─────────────┘ │
└────────────────────────┼────────────────────────────────────────┼───────────────┘
                         │                                        │
                         ▼                                        ▼
             ┌────────────────────────────────────────────────────────┐
             │            Multi-Account Session Store                 │
             │           (~/.genspark/profiles/<name>/)               │
             │  • storage_state.json (Private cookies 0o600)          │
             │  • recaptcha_token.txt (Anti-bot validation)           │
             └────────────────────────────────────────────────────────┘
```

---

## 2. Multi-Account Pool & Cross-Process State Architecture

### A. State File and Concurrency Control
All processes—whether simultaneous terminal commands (`gsk`), background agents calling MCP tools, or OpenAI HTTP proxy requests—read and write to a single centralized state file:
- **Location**: `~/.genspark/router_state.json`
- **Lock**: `~/.genspark/.router_state.lock` using POSIX non-blocking `fcntl.flock(fd, fcntl.LOCK_EX)` with exponential backoff retry.
- **Invariants**:
  - `in_flight` counters are strictly acquired before launching any request and guaranteed to be released in `finally` blocks.
  - Zombie `in_flight` counts caused by interrupted processes (`SIGKILL`) are bounded and auto-recovered.

### B. Routing Strategies
The `AccountRouter` implements three distinct strategies configured via `gsk config set strategy <mode>` or `gsk pool strategy <mode>`:

1. **`round-robin` (Default — Smart Least-Busy)**:
   - Rotates cyclically among healthy accounts.
   - When accounts have equal turn eligibility, ties are broken by selecting the account with the lowest active `in_flight` counter.
2. **`least-used`**:
   - Evaluates tuple `(in_flight, total_requests, last_used_timestamp)`.
   - Ensures optimal load distribution over long batch processing jobs.
3. **`failover`**:
   - Directs all traffic to the primary default account until it hits `max_concurrency_per_account` or enters a cooldown state, then seamlessly spills over to secondary accounts.

### C. Quota & Rate-Limit Interception State Machine
When communicating with Genspark's upstream backend, errors are classified into typed exceptions:
- **`QuotaExhaustedError`**: Triggered by HTTP `402 Payment Required` or by real-time SSE stream inspection detecting `"credit limit reached"`, `"quota exhausted"`, or `"insufficient balance"` chunks. Sets account cooldown to `1800s`.
- **`RateLimitError`**: Triggered by HTTP `429 Too Many Requests`. Sets account cooldown to `300s`.
- **`SessionExpiredError`**: Triggered by HTTP `401 Unauthorized` or missing session cookies. Marks account as unauthenticated.

Upon encountering any of the above, `AccountRouter.execute_with_failover()` transparently marks the failing account as unhealthy, records the cooldown timestamp in `router_state.json`, and immediately re-executes the request against the next available healthy profile without losing the user's prompt or streaming output.

---

## 3. Parallel Multi-Account Batch Engine

The `MultiAccountBatchExecutor` (`genspark_cli/batch.py`) coordinates high-throughput parallel execution across the entire account pool:

```
[User Batch Request: 50 Prompts]
               │
               ▼
   [Task Queue & Concurrency Limiter]
   (Bounded by pool size * max_concurrency)
               │
   ┌───────────┼───────────┐
   ▼           ▼           ▼
[Worker 1]  [Worker 2]  [Worker N]
   │           │           │
[Account A] [Account B] [Account C] (Auto-Failover Enabled)
   │           │           │
   └───────────┼───────────┘
               ▼
 [Progress Aggregator & Output Writer]
 (.jsonl streaming / rich terminal panel)
```

- **Async Semaphore Pool**: Overall parallelism is capped by either `--concurrency` or `pool_size * max_concurrency_per_account`.
- **Dynamic Task Distribution**: As soon as an account completes a prompt, it immediately picks up the next task from the queue.
- **Failover Retention**: If an account exhausts its quota mid-batch, the task is failed over to another account with retry counter tracking (`attempts` metric).

---

## 4. Human-First Interactive Menu & Onboarding Architecture

To eliminate command fatigue for non-technical users, `genspark_cli/menu.py` implements a numbered TTY navigation loop:

```
gsk (Terminal Check: isatty)
   │
   ├─► First run (0 logged-in accounts) ──► Guided 3-Step Onboarding
   │                                          1. Login primary account
   │                                          2. Optional secondary accounts
   │                                          3. Auto-configure round-robin
   │
   └─► Subsequent runs ──────────────────► Numbered Home Menu
                                              1. 💬 Chat with AI
                                              2. 👥 Account Manager
                                              3. 🎨 Image Generator
                                              4. ⚙️  Settings Wizard
                                              5. 📡 Live Health Ping
                                              6. ❓ Quick Guide
                                              0. Exit
```

- **Separation of Concerns**: Interactive numbered menus (`menu.py`) are strictly for human TTY sessions. Automated AI agents (Claude, Codex, Antigravity) use scripted commands (`gsk pool ...`, `gsk batch ...`, `gsk auth logout <name> -f`) or stdio MCP tools.

---

## 5. Universal 3-Agent Plugin Architecture

The suite conforms to the standard `.plugin` bundle specification for the top three agentic coding environments:

| Feature / Artifact | Google Antigravity (`agy`) | Anthropic Claude Code | OpenAI Codex |
| :--- | :--- | :--- | :--- |
| **Manifest Path** | `plugin.json` | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| **MCP Definition** | `mcp_config.json` | `.claude-plugin/plugin.json` (`mcpServers`) | `.mcp.json` |
| **MCP Entrypoint** | `bin/genspark-mcp` | `scripts/run-mcp.sh` | `./scripts/run-mcp.sh` |
| **Skills Discovery** | `skills/*/SKILL.md` | `skills/*/SKILL.md` | `skills/*/SKILL.md` |
| **Rule System** | `rules/AGENTS.md` | `rules/AGENTS.md` | `rules/AGENTS.md` |
| **Packaging Target** | Local directory link | Local directory link | Deterministic `.plugin` zip |

---

## 6. Security Model & Credentials Boundary

1. **Zero API Keys**: No API keys are ever stored, transmitted, or required.
2. **Private File Permissions**: All cookie sessions (`storage_state.json`) and tokens are saved with strict POSIX `0o600` permissions inside private directories (`0o700`).
3. **No Leakage to LLM Context**: Skills and rules explicitly forbid printing, inspecting, or echoing token contents into conversation transcripts.
4. **Offline Doctor Integrity**: `genspark doctor` operates 100% offline, inspecting local files without making external network calls that could leak environment details.
