# ⚡ Installation & Setup Guide — Genspark Master AI Suite

This guide walks you through setting up Genspark Master on your workstation or server, configuring it for **Google Antigravity**, **Claude Code**, **OpenAI Codex**, and setting up multi-account pool routing.

---

## 📋 System Requirements

- **Operating System**: macOS (Apple Silicon or Intel), Linux (Ubuntu, Debian, Fedora, Arch).
- **Python**: Python 3.10, 3.11, 3.12, 3.13, or 3.14.
- **Node.js** (Optional): For running third-party MCP bridges if needed.
- **Disk Space**: ~150 MB (excluding Playwright browser cache).

---

## 🚀 Fast Automated Install (Recommended)

Clone the repository and run the universal installer:

```bash
git clone https://github.com/tody-agent/genspark-master.git
cd genspark-master

# Standard installation (creates .venv, installs dependencies & Chromium for login)
./scripts/install.sh

# Or developer symlink mode (links directly to active AI agent directories)
./scripts/install.sh --link
```

### Installer Flags
| Option | Description |
| :--- | :--- |
| `--link` | Uses symlinks instead of copying (recommended for active development). |
| `--no-browser` | Skips Playwright/Chromium installation (CLI & MCP only, headless servers). |
| `--gemini`, `--antigravity` | Installs plugin specifically to `~/.gemini/config/plugins/genspark`. |
| `--claude` | Installs plugin specifically to `~/.claude/plugins/genspark`. |
| `--codex` | Installs plugin specifically to `~/.codex/plugins/genspark`. |
| `--all` | Installs to all detected platform directories (default). |

---

## 🔗 Global Terminal Commands Setup

To run `gsk` and `genspark` from any directory in your terminal, symlink the executables to `~/.local/bin/` (or any directory in your `$PATH`):

```bash
mkdir -p ~/.local/bin
ln -sf $(pwd)/bin/genspark ~/.local/bin/genspark
ln -sf $(pwd)/bin/gsk ~/.local/bin/gsk
ln -sf $(pwd)/bin/genspark-mcp ~/.local/bin/genspark-mcp
```

Verify that the CLI is accessible:
```bash
gsk --help
```

---

## 🔑 First-Run Onboarding & Account Management

### 1. Launch Interactive Onboarding
Run `gsk` in your terminal without any arguments:

```bash
gsk
```

If you do not have any logged-in accounts, `gsk` automatically starts the **3-Step Guided Onboarding**:
1. **Step 1: Primary Account Login**: Opens a browser window. Log in to your Genspark account, send any single message in the chat, and press Enter in the terminal to save your session.
2. **Step 2: Add Secondary Accounts (Optional)**: If you have additional accounts, add them now to increase throughput and enable automatic failover.
3. **Step 3: Routing Strategy**: If you have 2+ accounts, round-robin load balancing is automatically enabled.

### 2. Managing Accounts Later (`gsk accounts`)
You can manage accounts at any time by running:

```bash
gsk accounts
```

Or from within an interactive chat session, type `/accounts`, `/login`, or `/logout`.

Numbered options:
- `1` · Add a new account (browser login).
- `2` · Re-login to refresh an expired session.
- `3` · Logout (clears session cookies, keeps account name in config).
- `4` · Remove account permanently.
- `5` · Set as default account.
- `0` · Back to main menu.

---

## 🤖 AI Agent Integrations

### 1. Google Antigravity (`agy`)
Antigravity automatically loads plugins located in `~/.gemini/config/plugins/genspark`.

Verify the plugin installation:
```bash
agy plugin list
```
You should see:
```text
- genspark (enabled, 0.5.0)
    Components: 4 skills, 1 rule, 1 MCP server
```

To validate plugin integrity:
```bash
agy plugin validate /path/to/genspark-master
```

### 2. Anthropic Claude Code
Claude Code automatically discovers plugins in `~/.claude/plugins/genspark` via `.claude-plugin/plugin.json`.

Validate with Claude Code:
```bash
claude plugin validate /path/to/genspark-master
```

To add the stdio MCP server directly to Claude Code configuration:
```bash
claude mcp add genspark -- /path/to/genspark-master/bin/genspark-mcp
```

### 3. OpenAI Codex
Codex reads `.codex-plugin/plugin.json` and `.mcp.json`.

To build a standalone `.plugin` package for Codex distribution:
```bash
./scripts/package.sh
```
This generates:
- `dist/genspark-master-0.5.0.plugin`
- `dist/genspark-plugin-v0.5.0.tar.gz`
- `dist/genspark-plugin-v0.5.0.zip`

---

## 🧪 Diagnostics & Health Verification

Run the built-in diagnostic tools to confirm installation health:

```bash
# 1. Offline health check
gsk doctor --json

# 2. Check multi-account pool status and active routing strategy
gsk pool status

# 3. Live ping all logged-in accounts concurrently
gsk pool ping

# 4. Run the full unit test suite
./scripts/test_gate.sh
```
