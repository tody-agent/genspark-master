---
name: gen-chat
description: Use the Genspark CLI (`gsk` / `genspark`) and MCP server for one-shot chat, interactive Studio REPL, parallel multi-account batch execution (`gsk batch` / `batch_chat`), and auto-routed round-robin failover. Use when the user asks to chat through Genspark, run large parallel prompt batches across multiple accounts, compare answers, or manage chat sessions. Requires browser-authenticated Genspark sessions and never uses API keys.
---

# Chat & Multi-Account Parallel Execution through Genspark

Access leading AI Chat models — Anthropic Claude, OpenAI GPT-6/GPT-5, Google Gemini, DeepSeek, xAI Grok, Xiaomi MiMo, ZhipuAI GLM, and Moonshot Kimi — via Genspark's cross-process multi-account pool.

## Prerequisites & Multi-Account Pool Health

Verify local session and account pool readiness without exposing credential tokens:

```bash
gsk doctor --json
gsk pool status
```

If login is missing or expired, ask the user to run `gsk auth login` or add more accounts with `gsk pool add <name>`.

## Available Chat Models & Credit Multipliers

### 🔥 Recommended Models (Top Tier & High Efficiency)

| Model ID | Name | Provider | Tier | Multiplier | Reasoning | Context Window | Key Features / Best For |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `claude-opus-5.5` ★ | Claude Opus 5.5 | Anthropic | Ultra | 4.0× | **Yes** | 1,000,000 | **Default Model**. Flagship deep reasoning, code refactoring & UI/UX analysis. |
| `deepseek-v4.1-flash` 🔥 | DeepSeek V4.1 Flash | DeepSeek | Fast | 0.3× | No | 200,000 | Ultra-fast, high-efficiency logic & rapid prototyping. |
| `glm-5.3-flash` 🔥 | GLM-5.3 Flash | ZhipuAI | Fast | 0.15× | No | 200,000 | Extreme low-cost, high-speed drafting & parsing. |
| `gpt-6-sol` 🔥 | GPT-6 Sol | OpenAI | Premium | 2.0× | No | 200,000 | Next-generation OpenAI flagship architecture. |

### 🧠 Anthropic Claude Lineup

| Model ID | Name | Tier | Multiplier | Reasoning | Context Window | Key Features / Best For |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `claude-opus-5.5` ★ | Claude Opus 5.5 | Ultra | 4.0× | Yes | 1,000,000 | Flagship reasoning & architectural synthesis. |
| `claude-opus-5` | Claude Opus 5 | Ultra | 5.0× | Yes | 1,000,000 | Claude 5 Opus reasoning model. |
| `claude-opus-4-8` | Claude Opus 4.8 | Ultra | 5.0× | Yes | 1,000,000 | Claude Opus 4.8 reasoning model. |
| `claude-opus-4-7` | Claude Opus 4.7 | Ultra | 5.0× | Yes | 1,000,000 | Claude Opus 4.7 reasoning engine. |
| `claude-opus-4-6` | Claude Opus 4.6 | Premium | 5.0× | No | 200,000 | High-capacity reasoning & code review. |
| `claude-sonnet-5.5` | Claude Sonnet 5.5 | Premium | 2.0× | No | 200,000 | Balanced everyday tasks & UI design. |
| `claude-sonnet-5` | Claude Sonnet 5 | Premium | 2.0× | No | 200,000 | Next-gen Claude 5 Sonnet. |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 | Fast | 3.0× | No | 200,000 | Balanced everyday tasks. |
| `claude-haiku-5.5` | Claude Haiku 5.5 | Fast | 0.1× | No | 200,000 | Ultra-fast low-credit helper. |
| `claude-haiku-4.5` | Claude Haiku 4.5 | Fast | 1.0× | No | 200,000 | Low-latency lightweight execution. |

### ⚡ OpenAI, Google Gemini, DeepSeek, ZhipuAI, Xiaomi, Kimi & xAI

| Model ID | Name | Provider | Tier | Multiplier | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gpt-6.1-sol` | GPT-6.1 Sol | OpenAI | Premium | 2.0× | Advanced GPT-6.1 logic. |
| `gpt-6-sol` 🔥 | GPT-6 Sol | OpenAI | Premium | 2.0× | OpenAI flagship architecture. |
| `gpt-6-luna` | GPT-6 Luna | OpenAI | Fast | 0.1× | Fast & ultra-efficient GPT-6. |
| `gpt-5.4` | GPT-5.4 | OpenAI | Premium | 3.0× | Standard GPT-5.4 flagship. |
| `gemini-3.8-flash` | Gemini 3.8 Flash | Google | Fast | 0.75× | Latest high-speed multimodal Flash. |
| `gemini-3.1-pro-preview` | Gemini 3.1 Pro Preview | Google | Premium | 2.0× | Pro reasoning & long context. |
| `deepseek-v4.1-flash` 🔥 | DeepSeek V4.1 Flash | DeepSeek | Fast | 0.3× | High-efficiency Chinese/English coding. |
| `glm-5.3-flash` 🔥 | GLM-5.3 Flash | ZhipuAI | Fast | 0.15× | Ultra-low cost fast inference. |
| `mimo-v2.6-pro` | MiMo V2.6 Pro | Xiaomi | Fast | 0.435× | Xiaomi advanced Pro reasoning. |
| `kimi-k3` | Kimi K3 | Moonshot | Premium | 3.0× | Long-context Chinese research. |
| `grok-4.7` | Grok 4.7 | xAI | Premium | 2.0× | Real-time perspective & logic. |

## Agentic CLI Execution (Claude Code / Hermes Style)

```bash
# Launch Interactive Agentic Studio REPL (with HUD status bar & tab autocomplete)
gsk

# Zero-friction one-shot prompt (auto-routes across healthy accounts in pool)
gsk "Analyze this UX issue"
gsk "Review this architecture" -m claude-opus-5.5
git diff | gsk "Review these changes" -r

# Multi-account parallel batch execution for large projects (no waiting)
gsk batch "Task 1" "Task 2" "Task 3" -m claude-opus-5.5 --concurrency 6
gsk batch --input-file tasks.jsonl --output results.jsonl --concurrency 6 --json

# Classic subcommands remain 100% supported
genspark chat ask "Analyze this UX issue" --model claude-opus-5.5
genspark models list --json
```

## Multi-Account Routing & Strict Model Integrity

- **Auto-Routing & Round-Robin (`round-robin` + `least-busy`)**: Requests automatically rotate across all healthy profiles in `~/.genspark/profiles/*` and prioritize accounts with the fewest active in-flight requests.
- **Instant Failover**: If an account hits `QuotaExhaustedError` (HTTP 402 or SSE credit limit), `RateLimitError` (HTTP 429), `SessionExpiredError`, or `RecaptchaError`, `AccountRouter` places that account into cooldown and immediately retries on the next healthy account.
- **Strict Stop & Cooldown**: The router never silently downgrades your chosen model. If all accounts in the pool are in cooldown or out of credits, it stops and reports the exact cooldown timer and status for each account (`gsk pool status` / `gsk pool reset`).
