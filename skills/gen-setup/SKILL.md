---
name: gen-setup
description: Install, verify, or configure the Genspark Master CLI, Multi-Account Pool, and MCP bridge using browser-session authentication. Use when a user asks to install Genspark, set up browser login, manage multiple accounts, configure round-robin routing, diagnose the local installation, or register genspark-mcp. Never introduce Genspark API-key authentication.
---

# Set up Genspark Master & Multi-Account Pool

Use the plugin's repository-local virtual environment and preserve all existing user configuration.

## Interactive Onboarding & Account Manager (preferred for humans)

Tell non-technical users to just run `gsk` in their own terminal (the menu needs a real TTY; agents cannot drive it):

- First run with no logged-in account launches a 3-step onboarding (login -> optional extra accounts -> auto round-robin when 2+ accounts). Re-run with `gsk setup`.
- Afterwards `gsk` opens a numbered menu: Chat, Accounts, Image, Settings, Health check, Quick guide.
- `gsk accounts` (or `/accounts`, `/login`, `/logout` inside chat) manages accounts: add, re-login, logout (clear session, keep name), remove, set default.
- Agents must not run these interactive flows; use the scripted commands below (`pool add`, `pool import`, `auth logout <name> -f`, `pool status --json`) or ask the user to run `gsk accounts`.

## Install

From the plugin root, run:

```bash
./scripts/install.sh
```

Use `./scripts/install.sh --no-browser` only when Playwright/Chromium is intentionally omitted and an existing browser session will be supplied separately.

The installer must not edit shell profiles, global `PATH`, MCP JSON, or third-party configuration. Use the absolute executables printed by the installer.

## Verify and Authenticate (Single or Multi-Account Pool)

Run the offline diagnostic first:

```bash
.venv/bin/genspark doctor --json
.venv/bin/genspark pool status --json
```

If `browser_session` is `missing`, ask the user to complete the headed browser flow:

```bash
# Login default account
.venv/bin/genspark auth login

# Add multiple accounts to the pool for parallel execution & round-robin failover
.venv/bin/genspark pool add work acc2 acc3

# Or import an existing Playwright storage_state.json directly
.venv/bin/genspark pool import acc2 /path/to/storage_state.json --token "<recaptcha_token>"
```

Do not inspect, print, or copy cookie and reCAPTCHA token contents. Confirm health across all accounts with:

```bash
.venv/bin/genspark pool status
.venv/bin/genspark pool ping
```

## Configure Routing Strategy & Concurrency (`gsk config` / `gsk pool`)

Genspark Master synchronizes multi-account routing across processes via `~/.genspark/router_state.json` (protected with `0o600` permissions and file locks):

```bash
# View current configuration
gsk config show

# Set routing strategy: round-robin (default + least-busy) | least-used | failover
gsk pool strategy round-robin
gsk config set concurrency 3
gsk config set model claude-opus-5.5
gsk config set image-model nano-banana-2

# Clear cooldown / quota-exhausted flags across the pool
gsk pool reset
```

## Register MCP Only When Requested

Use the absolute `.venv/bin/genspark-mcp` path. Prefer the target client's supported command. When editing JSON, parse it and merge only `mcpServers.genspark`; never overwrite the full file. Show the proposed mutation before applying it unless the user explicitly asked for automatic configuration.

Example entry:

```json
{"mcpServers":{"genspark":{"command":"/absolute/path/to/genspark-master/.venv/bin/genspark-mcp"}}}
```

Finish by running `genspark capabilities --json` and `genspark doctor --json` from the virtual environment.
