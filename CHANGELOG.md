# 📜 Changelog

All notable changes to the **Genspark Master AI Suite** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] - 2026-10-24

### 🚀 Added
- **Interactive Home Menu & First-Run Onboarding (`gsk`, `gsk menu`, `gsk setup`)**:
  - Pure numbered-choice interactive terminal UI designed for humans (`menu.py`).
  - First-time guided 3-step setup: primary login, optional secondary accounts, and automatic routing strategy configuration.
  - Interactive account management via `gsk accounts` (add, re-login, logout, remove, set default) and in-chat slash commands (`/accounts`, `/login`, `/logout`, `/menu`).
- **Universal Multi-Platform `.plugin` Integration**:
  - **Google Antigravity**: Native `plugin.json` manifest and `mcp_config.json` registering 4 skills, 1 rule (`rules/AGENTS.md`), and 1 MCP server.
  - **Claude Code**: Native `.claude-plugin/plugin.json` supporting `${CLAUDE_PLUGIN_ROOT}/scripts/run-mcp.sh` and global skill discovery.
  - **OpenAI Codex**: Native `.codex-plugin/plugin.json` manifest, `.mcp.json`, and deterministic `.plugin` zip packaging.
- **Cross-Process Multi-Account Pool & Auto-Failover**:
  - `AccountRouter` with persistent state in `~/.genspark/router_state.json` synchronized across CLI, MCP, and proxy processes via `fcntl.flock`.
  - 3 routing strategies: `round-robin` (smart *least-busy* load balancing), `least-used`, and `failover`.
  - Instant quota & rate-limit failover: detects HTTP 402, HTTP 429, and inline SSE credit-exhausted messages, placing the exhausted account in cooldown and rotating to the next healthy account.
  - Strict Model Integrity: stops and reports cooldown timers when all accounts are exhausted rather than silently downgrading models.
- **Parallel Multi-Account Batch Engine**:
  - `gsk batch`: Execute tens or hundreds of chat prompts or image generation tasks concurrently across all accounts in the pool (`-c/--concurrency`).
  - Supports inline prompts, `.jsonl`/`.json`/`.txt` task files, and structured output files.
  - MCP tools: `batch_chat` and `batch_generate_images` for parallel multi-agent workflows.
- **Master Orchestrator Skill (`skills/genspark/SKILL.md`)**:
  - Complete decision matrix and playbooks for Google Antigravity, Claude Code, and Codex agents to leverage the multi-account pool, batch tools, and agentic CLI.
- **Expanded Model Lineup**:
  - **40 Chat Models**: Claude Opus 5.5, Claude Opus 4.7, GPT-6 Sol, GPT-6.1 Sol, GPT-5.4, Gemini 3.8 Flash, DeepSeek V4.1 Flash, GLM-5.3 Flash, Xiaomi MiMo, Moonshot Kimi, and xAI Grok.
  - **9 Image Generation Models**: Flux 2 Pro, GPT Image 2, Nano Banana 2, Seedream v5 Lite, Z-Image Turbo, Nano Banana Pro, and Flux 2 up to 4K resolution.
- **9 MCP Tools (`genspark:*`)**:
  - `chat`, `chat_with_context`, `batch_chat`, `generate_image`, `batch_generate_images`, `configure_pool`, `get_models`, `list_image_models`, `check_status`.

### ⚡ Changed
- Upgraded `scripts/install.sh` to link contents and preserve zero-redundant `.venv` disk footprint on local SSDs while maintaining full compatibility with `agy plugin list` and `claude plugin validate`.
- Upgraded `scripts/build_plugin.py` to package `.claude-plugin`, `plugin.json`, `mcp_config.json`, and `rules/AGENTS.md` into distributable archives.
- Enhanced REPL in `interactive.py` with HUD header bar, command history (`~/.genspark/repl_history`), and slash command completion.

---

## [0.4.0] - 2026-10-13

### 🚀 Added
- Direct HTTP client (`GensparkClient`) bypassing browser overhead for real-time SSE streaming chat.
- Autonomous Code Runner (`genspark run -x`) extracting and executing Python/Bash snippets locally.
- Persistent conversation store with automatic multi-turn summarization and context management (`/session`, `/history`, `/compact`).

---

## [0.3.0] - 2026-09-25

### 🚀 Added
- Generative AI image pipeline (`genspark image generate`) with 170+ art styles and 14 aspect ratios.
- Local OpenAI-compatible REST proxy server (`genspark server start`) at `http://127.0.0.1:8080/v1`.

---

## [0.2.0] - 2026-08-20

### 🚀 Added
- Multi-profile management (`genspark auth add`, `switch`, `list`, `logout`).
- Model Context Protocol (MCP) server for stdio clients.

---

## [0.1.0] - 2026-08-06

### 🚀 Added
- Initial release with browser session state authentication (`storage_state.json`).
- Core chat interface supporting Claude Opus 4.7 and GPT-5.4.
