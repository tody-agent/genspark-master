# Design: Browser-Token Plugin Hardening

## Context & Technical Approach

Restore the missing Python runtime behind the existing CLI contracts, then package it as `genspark-master`. Browser automation owns login/token capture; atomic session storage owns credentials; shared HTTP clients own Genspark requests; CLI, MCP, and proxy layers remain adapters.

The implementation adopts local capability discovery, short aliases, diagnostics, configuration precedence, and stdout/stderr separation from the official npm CLI. It explicitly rejects that CLI's persisted API-key authentication model.

## Proposed Changes

### Plugin and packaging

Create the canonical plugin/MCP manifests, standardized skill packages, coherent Python extras, and `gsk` alias. Do not update an external marketplace.

### Credential boundary

Create atomic `0600` persistence utilities, centralize profile validation, reject symlinks/path traversal, and preserve existing profile data.

### Browser authentication

Restore a Playwright-first adapter that captures storage state and a reCAPTCHA token from an authenticated browser request. Expose an adapter seam for deterministic tests and use one bounded refresh attempt.

### Shared chat and MCP runtime

Restore the async chat client and FastMCP entrypoint. Both use the existing account router, typed errors, and browser-token sessions; no API-key input exists.

### Agent-native command contracts

Add offline `capabilities` and `doctor` commands. Keep machine output parseable on stdout and diagnostics on stderr.

### Installation and documentation

Replace destructive shell-profile edits with a deterministic local virtual-environment installer. Align README and skills with verified commands only.

## Verification

- Red-green tests for packaging, storage security, auth orchestration, client SSE/retry behavior, MCP failover, CLI output, installer safety, and gate coverage.
- Existing proxy, model, image, business, syntax, and secret tests remain green.
- Complete pytest, compileall, plugin validation, wheel build, isolated install, and console-script smoke tests pass.
- Live browser login remains a redacted manual smoke test because it requires the user's account.

