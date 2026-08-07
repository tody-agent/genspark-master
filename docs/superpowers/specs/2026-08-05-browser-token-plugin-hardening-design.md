# Design: Genspark Master Browser-Token Plugin Hardening

Date: 2026-08-05
Status: Approved direction, pending written-spec review

## Context

`genspark-master` is intended to expose Genspark chat and image generation through a Python CLI, an OpenAI-compatible proxy, MCP tools, and Codex skills. Its defining constraint is authentication through a real browser session: Playwright or CloakBrowser captures Genspark cookies and a reCAPTCHA token, then normal requests use those browser-derived credentials through HTTP.

The current workspace is incomplete as an installable Codex plugin:

- `.codex-plugin/plugin.json` and `.mcp.json` are absent.
- Skills are flat Markdown files rather than `skills/<skill-name>/SKILL.md` packages.
- Runtime references to `genspark_cli.auth`, `genspark_cli.client`, and `genspark_cli.mcp` cannot resolve because those modules are absent.
- `scripts/install.sh` installs `.[all]`, but `pyproject.toml` does not define an `all` extra.
- The README references documents that are absent from this workspace.
- Session and profile files are written non-atomically and without explicit private permissions.
- Profile lookup and deletion do not apply the same strict name validation as profile creation.
- The test gate omits `tests/test_06_image_models.py` and has no installation or entrypoint smoke test.

The official `@genspark/cli` 1.5.0 package provides useful agent-native CLI patterns: browser login, short aliases, capability discovery, deterministic config precedence, clean machine output, local file handling, skill initialization, and explicit diagnostics. Its login persists an API key, so its authentication implementation is not compatible with this project's browser-token-only constraint.

## Goals

1. Restore a runnable Python CLI, proxy, and MCP server around browser-derived cookies and reCAPTCHA tokens.
2. Package the workspace as a validation-ready Codex plugin named `genspark-master`.
3. Adopt the official CLI's strongest interface patterns without adopting API-key authentication.
4. Make installation repeatable and diagnosable on macOS and Linux with Python 3.10+.
5. Protect browser session material with private, atomic persistence and safe profile paths.
6. Prove behavior with test-first development, plugin validation, packaging checks, and entrypoint smoke tests.

## Non-Goals

- Persisting or accepting `GSK_API_KEY` or another Genspark API key.
- Reproducing all 90+ official Tool API commands.
- Adding email, calendar, connector, mesh, stock, social, or autonomous-agent features.
- Reverse-engineering additional private Genspark endpoints unrelated to the existing chat and image flows.
- Background self-updates.
- Updating a personal or team Codex marketplace outside this workspace without a separate explicit request.

## Options Considered

### A. Harden the existing browser-token core and adopt agent-native CLI contracts

Restore missing modules, standardize output and configuration, add diagnostics and capability discovery, secure session persistence, and package the repository correctly.

This option is selected because it directly improves the requested plugin while preserving its defining authentication boundary.

### B. Wrap the official npm CLI as a sidecar

This would expose many capabilities quickly, but its browser login stores an API key and creates a second runtime and configuration model. It violates the authentication constraint and is rejected.

### C. Port official Tool API parity onto browser cookies

This would require broad private-endpoint discovery and ongoing compatibility work. It has high maintenance and account-risk costs and is rejected for this initiative.

## Architecture

### 1. Codex plugin shell

The existing root remains the plugin root and must match the normalized plugin name `genspark-master`.

- `.codex-plugin/plugin.json` declares metadata, `./skills/`, and `./.mcp.json`.
- `.mcp.json` starts the installed `genspark-mcp` stdio server.
- Skills move to:
  - `skills/gen-setup/SKILL.md`
  - `skills/gen-chat/SKILL.md`
  - `skills/gen-imagegen/SKILL.md`
- `scripts/install.sh` installs the Python package and browser runtime without mutating unrelated agent configuration.
- Plugin validation uses the canonical `plugin-creator` validator.

No marketplace file is updated in this change. The plugin remains portable as a directory, and installation documentation explains how to install or link it. A later explicit request may add it to a personal marketplace.

### 2. Browser-token authentication boundary

`genspark_cli.auth` owns all browser interaction.

1. Launch a headed browser by default.
2. Let the user complete Genspark login.
3. Capture Playwright storage state and a reCAPTCHA token only after a valid authenticated session is detected.
4. Persist the data through `SessionManager` under the selected profile.
5. Close the browser and return a structured login result.

The CLI must not accept, derive, print, or store a Genspark API key. Chat and image clients receive only a `SessionManager` and build requests from its cookies and reCAPTCHA token.

Automatic refresh may launch browser automation using the saved storage state. If a visible challenge requires human action, the client returns a typed re-login requirement instead of looping indefinitely.

### 3. Session and configuration model

Configuration precedence follows the pattern learned from the official CLI:

1. CLI option.
2. Environment variable.
3. Profile/global configuration file.
4. Built-in default.

The existing `GENSPARK_SESSION_DIR`, logging variables, and command options remain supported. A new `--config` mechanism is not required for the first implementation because named profile directories already provide isolation; configuration resolution will be centralized so a later profile-file override can be added without changing consumers.

Session persistence must:

- Create directories with private permissions where supported.
- Write temporary files beside the destination.
- Flush and atomically rename the temporary file.
- Set credential-bearing files to mode `0600` on POSIX.
- Reject symlink cycles and unsafe path traversal.
- Preserve valid existing fields during updates.

All profile-taking operations validate names against one shared rule before resolving a path. Destructive profile deletion may only target a validated direct child of the profiles directory.

### 4. Restored runtime modules

#### `genspark_cli.auth`

Provides `run_login()` and `_refresh_recaptcha_token()` as expected by the current CLI and image client. It supports Playwright, with CloakBrowser as an optional adapter when installed.

#### `genspark_cli.client`

Provides `GensparkClient` and `run_chat()` as expected by the CLI, REPL, router, and proxy. It owns HTTP request construction, SSE parsing, typed errors, one bounded token-refresh retry, and conversation project chaining.

#### `genspark_cli.mcp`

Provides `run_mcp_server()` for the existing `genspark-mcp` entrypoint. MCP tools delegate to the same account router and client code as the CLI so failover and authentication behavior are not duplicated.

### 5. Agent-native CLI contracts

The command surface keeps existing commands and adds a small compatibility layer inspired by `@genspark/cli`:

- Both `genspark` and `gsk` console entrypoints invoke the same Click application.
- `genspark capabilities` returns available local capabilities and their authentication requirements.
- `genspark doctor` checks Python version, optional dependencies, browser availability, plugin/MCP paths, profile health, and missing runtime files. `--json` produces a stable machine-readable result.
- Existing `--json` command modes remain supported.
- Machine results go to stdout; progress, warnings, diagnostics, and debug output go to stderr.
- Error JSON is accompanied by a non-zero process exit status.
- Human output remains the default for interactive commands.

Capability discovery is local and deterministic for this release. It reports implemented chat, proxy, MCP, and image features; it does not fetch official Tool API schemas or imply support for unavailable commands.

### 6. Installation and skill initialization

`pyproject.toml` defines coherent extras:

- `browser`: Playwright login support.
- `stealth`: optional CloakBrowser support.
- `server`: OpenAI-compatible proxy requirements.
- `mcp`: MCP server requirements.
- `dev`: tests and validation support.
- `all`: the supported runtime extras used by the installer.

The installer:

1. Verifies it is running from the plugin root.
2. Creates or reuses `.venv`.
3. Installs the selected runtime extras.
4. Installs Chromium only when Playwright is selected.
5. Creates user-level command links only after resolving explicit absolute targets.
6. Does not silently edit shell profiles or third-party MCP configuration.
7. Runs `genspark doctor --json` and prints precise next actions.

The setup skill explains agent-specific MCP registration as an explicit, merge-safe step. It never overwrites an existing configuration object.

## Data Flow

```text
User -> genspark auth login
     -> headed browser -> Genspark login
     -> SessionManager atomic private files

CLI / MCP / OpenAI proxy
     -> AccountRouter selects profile
     -> GensparkClient or GensparkImageClient
     -> cookies + reCAPTCHA token from SessionManager
     -> Genspark internal chat/image endpoint
     -> SSE parser / response adapter
     -> stdout JSON, terminal text, MCP result, or OpenAI response
```

No API key enters this flow.

## Error Handling

- Missing session: typed `SessionExpiredError` with `genspark auth login` guidance.
- Expired reCAPTCHA token: one browser refresh attempt, then a typed `RecaptchaError`.
- Rate limit or unhealthy profile: account router cooldown and bounded failover.
- Invalid profile name: reject before filesystem resolution.
- Browser unavailable: diagnostic error listing the install command.
- MCP optional dependency missing: CLI remains usable; `doctor` reports the missing extra.
- Invalid JSON/config: fail closed for credential updates, with no partial overwrite.
- Broken install/entrypoint: caught by smoke tests before release.

## Testing Strategy

All production behavior follows red-green-refactor.

1. Packaging tests assert required plugin files, skill layout, manifest paths, and entrypoints.
2. Authentication tests use a browser adapter seam and verify cookie/token capture without network calls.
3. Session tests verify atomic replacement, POSIX permissions, invalid profile rejection, and containment for deletion.
4. Client tests feed recorded synthetic SSE lines and verify payload construction, conversation chaining, refresh bounds, and typed errors.
5. Output tests capture stdout/stderr and verify parseable JSON plus non-zero error exits.
6. Doctor tests cover healthy, degraded, and missing-optional-dependency states.
7. MCP tests invoke tool functions with a fake client/router and verify shared failover behavior.
8. Existing proxy, business logic, model, image parser, and security tests remain green.
9. Installation smoke tests build a wheel, install it into an isolated temporary virtual environment, and run both `genspark --help` and `gsk --help`.
10. Final verification runs the complete pytest suite, `scripts/test_gate.sh`, wheel build/install smoke test, and `plugin-creator/scripts/validate_plugin.py`.

Live Genspark login and generation are documented as a manual smoke test because they require the user's browser session and external account. Automated tests must never persist real tokens.

## Compatibility and Migration

- Existing `~/.genspark` profiles and storage state remain readable.
- The first successful write upgrades file permissions and uses atomic persistence.
- Existing `genspark` commands and aliases remain available.
- The new `gsk` alias is additive.
- Existing OpenAI-compatible endpoints remain unchanged.
- Unsupported documentation claims are corrected rather than emulated.

## Acceptance Criteria

1. The plugin validator accepts the plugin root with no placeholders.
2. `python -m build` succeeds and an isolated install exposes `genspark`, `gsk`, and `genspark-mcp`.
3. `genspark --help`, `gsk --help`, `genspark doctor --json`, and `genspark capabilities --json` succeed without a logged-in account.
4. The runtime contains resolvable `auth`, `client`, and `mcp` modules with tests for their public contracts.
5. No API-key option, environment variable, or persisted API-key field is introduced.
6. Browser-derived cookie and reCAPTCHA files are written atomically with private POSIX permissions.
7. Invalid or traversal-like profile names cannot read or delete paths outside the profile root.
8. Machine-output commands produce valid JSON on stdout and keep diagnostics on stderr.
9. All automated tests and the complete test gate pass.
10. README and setup skills document the verified installation and browser-token login flow accurately.

