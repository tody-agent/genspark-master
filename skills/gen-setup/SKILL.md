---
name: gen-setup
description: Install, verify, or configure the Genspark Master CLI and MCP bridge using browser-session authentication. Use when a user asks to install Genspark, set up browser login, diagnose the local installation, register genspark-mcp, or configure a Genspark profile. Never introduce Genspark API-key authentication.
---

# Set up Genspark Master

Use the plugin's repository-local virtual environment and preserve all existing user configuration.

## Install

From the plugin root, run:

```bash
./scripts/install.sh
```

Use `./scripts/install.sh --no-browser` only when Playwright/Chromium is intentionally omitted and an existing browser session will be supplied separately.

The installer must not edit shell profiles, global `PATH`, MCP JSON, or third-party configuration. Use the absolute executables printed by the installer.

## Verify and authenticate

Run the offline diagnostic first:

```bash
.venv/bin/genspark doctor --json
```

If `browser_session` is `missing`, ask the user to complete the headed browser flow:

```bash
.venv/bin/genspark auth login
```

Do not inspect, print, or copy cookie and reCAPTCHA token contents. Confirm health with `auth status` or `doctor --json`.

## Register MCP only when requested

Use the absolute `.venv/bin/genspark-mcp` path. Prefer the target client's supported command. When editing JSON, parse it and merge only `mcpServers.genspark`; never overwrite the full file. Show the proposed mutation before applying it unless the user explicitly asked for automatic configuration.

Example entry:

```json
{"mcpServers":{"genspark":{"command":"/absolute/path/to/genspark-master/.venv/bin/genspark-mcp"}}}
```

Finish by running `genspark capabilities --json` and `genspark doctor --json` from the virtual environment.
