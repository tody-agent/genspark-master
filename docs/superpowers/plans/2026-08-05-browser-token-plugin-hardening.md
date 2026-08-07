# Browser-Token Plugin Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore, secure, and package `genspark-master` as an installable Codex plugin that uses browser-derived cookies and reCAPTCHA tokens as its only Genspark authentication material.

**Architecture:** The existing Python CLI remains the product core. A headed browser adapter captures session state, `SessionManager` persists it atomically, shared HTTP clients consume it, and CLI/MCP/OpenAI surfaces delegate to those clients. The Codex plugin shell discovers standardized skills and the installed MCP entrypoint.

**Tech Stack:** Python 3.10+, Click, httpx, aiohttp, Rich, Pydantic, Playwright, optional CloakBrowser, FastMCP, pytest, setuptools/build, Codex plugin manifests.

## Global Constraints

- Genspark authentication is browser-derived cookies plus reCAPTCHA token only; do not add `GSK_API_KEY`, `--api-key`, or an API-key field.
- Preserve compatibility with existing `~/.genspark` profile and storage-state files.
- Browser login is headed by default; an unattended refresh is bounded to one attempt.
- Machine results use stdout; progress, warnings, debug messages, and errors use stderr.
- Python support remains `>=3.10`.
- Plugin root and manifest name are exactly `genspark-master`.
- Do not modify a personal/team marketplace in this initiative.
- Do not repair, replace, or initialize `.git`; current Git metadata is invalid. Commit steps are conditional on `git rev-parse --is-inside-work-tree` returning success.
- Apply TDD to production behavior. The `plugin-creator` scaffold files are the approved configuration-only exception.

---

## File Structure

### Create

- `.codex-plugin/plugin.json` — Codex plugin metadata and component paths.
- `.mcp.json` — stdio MCP server declaration.
- `genspark_cli/storage.py` — atomic private file writes and direct-child path validation.
- `genspark_cli/auth.py` — browser adapters, login capture, and bounded token refresh.
- `genspark_cli/client.py` — browser-token chat HTTP client and synchronous CLI wrapper.
- `genspark_cli/mcp.py` — lazy FastMCP registration and shared tool implementations.
- `genspark_cli/capabilities.py` — deterministic local capability registry.
- `genspark_cli/doctor.py` — machine-readable installation/session diagnostics.
- `tests/test_07_plugin_packaging.py` — plugin and Python packaging contract.
- `tests/test_08_session_security.py` — atomic persistence and path containment.
- `tests/test_09_auth.py` — browser adapter orchestration without real credentials.
- `tests/test_10_client.py` — payload, SSE, retry, and response behavior.
- `tests/test_11_mcp.py` — MCP service delegation and optional dependency behavior.
- `tests/test_12_cli_contracts.py` — stdout/stderr, diagnostics, and aliases.
- `tests/test_13_installation.py` — installer and skill-layout safety.
- `skills/gen-setup/SKILL.md`, `skills/gen-chat/SKILL.md`, `skills/gen-imagegen/SKILL.md` — canonical skill packages.

### Modify

- `pyproject.toml` — coherent extras and `gsk` entrypoint.
- `genspark_cli/session.py` — atomic private persistence.
- `genspark_cli/profiles.py` — shared profile validation and safe deletion.
- `genspark_cli/cli.py` — capabilities/doctor commands and stderr-safe errors.
- `genspark_cli/image_client.py` — reuse bounded browser-token refresh contract.
- `scripts/install.sh` — deterministic installer with no shell-profile mutation.
- `scripts/test_gate.sh` — run every test layer, including image and packaging tests.
- `README.md` — verified feature, install, auth, diagnostics, and Codex plugin documentation.
- `requirements.txt` — keep core dependencies synchronized with `pyproject.toml`.
- `.cm/CONTINUITY.md` — execution and verification state.

### Remove after canonical copies exist

- `skills/gen-setup.md`
- `skills/gen-chat.md`
- `skills/gen-imagegen.md`

---

### Task 1: Scaffold and lock the plugin/packaging contract

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `.mcp.json`
- Create: `tests/test_07_plugin_packaging.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: console scripts `genspark`, `gsk`, and `genspark-mcp`.
- Produces: manifest paths `skills="./skills/"` and `mcpServers="./.mcp.json"`.
- Consumes: existing `genspark_cli.cli:main`; later tasks provide `genspark_cli.mcp:run_mcp_server`.

- [ ] **Step 1: Run the approved configuration scaffold**

Run from the plugin-creator skill root:

```bash
python3 scripts/create_basic_plugin.py genspark-master \
  --path /Volumes/Builder/Skills \
  --with-skills --with-scripts --with-mcp
```

Expected: creates only `.codex-plugin/plugin.json` and `.mcp.json`; existing source directories remain intact. Do not use `--force` and do not pass `--with-marketplace`.

- [ ] **Step 2: Write the packaging contract test**

```python
def test_plugin_manifest_matches_root_and_components():
    manifest = json.loads(Path('.codex-plugin/plugin.json').read_text())
    assert manifest['name'] == 'genspark-master'
    assert manifest['skills'] == './skills/'
    assert manifest['mcpServers'] == './.mcp.json'
    assert Path('.mcp.json').is_file()


def test_python_entrypoints_include_short_alias_and_mcp():
    payload = tomllib.loads(Path('pyproject.toml').read_text())
    scripts = payload['project']['scripts']
    assert scripts == {
        'genspark': 'genspark_cli.cli:main',
        'gsk': 'genspark_cli.cli:main',
        'genspark-mcp': 'genspark_cli.mcp:run_mcp_server',
    }
    assert {'browser', 'stealth', 'server', 'mcp', 'dev', 'all'} <= set(
        payload['project']['optional-dependencies']
    )
```

- [ ] **Step 3: Run the test and verify RED**

Run: `.venv/bin/python -m pytest tests/test_07_plugin_packaging.py -q`

Expected: FAIL because the scaffold metadata is generic, `gsk` is absent, and `all` is undefined. If `.venv` does not exist, create it and install only the development harness first:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

- [ ] **Step 4: Write final manifest, MCP declaration, and package metadata**

Use version `0.5.0` for both Python and plugin manifests. The manifest must contain real author/interface values, an array of at most three default prompts, and no unsupported `hooks` field. `.mcp.json` must be:

```json
{
  "mcpServers": {
    "genspark": {
      "command": "genspark-mcp",
      "args": []
    }
  }
}
```

Add `gsk = "genspark_cli.cli:main"`. Define `all` using the runtime dependencies from `browser`, `server`, and `mcp`; keep `dev` separate and include `pytest`, `pytest-asyncio`, and `build`.

- [ ] **Step 5: Run the test and plugin validator**

Run: `.venv/bin/python -m pytest tests/test_07_plugin_packaging.py -q`

Expected: PASS.

Run:

```bash
python3 /Users/todyle/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  /Volumes/Builder/Skills/genspark-master
```

Expected: manifest validation succeeds. MCP executable resolution is verified after Task 5.

- [ ] **Step 6: Commit conditionally**

If Git is valid:

```bash
git add .codex-plugin/plugin.json .mcp.json pyproject.toml tests/test_07_plugin_packaging.py
git commit -m "build: scaffold genspark Codex plugin"
```

Otherwise record `commit skipped: invalid workspace Git metadata` and continue without modifying `.git`.

---

### Task 2: Make session persistence private, atomic, and path-contained

**Files:**
- Create: `genspark_cli/storage.py`
- Create: `tests/test_08_session_security.py`
- Modify: `genspark_cli/session.py`
- Modify: `genspark_cli/profiles.py`

**Interfaces:**
- Produces: `atomic_write_text(path: Path, content: str, mode: int = 0o600) -> None`.
- Produces: `validate_profile_name(name: str) -> str`.
- Produces: `direct_child(root: Path, name: str) -> Path`.
- Consumes: standard `Path`, `os`, `tempfile`, and JSON only.

- [ ] **Step 1: Write failing security tests**

```python
def test_session_files_are_private_and_replace_atomically(tmp_path):
    session = SessionManager(str(tmp_path))
    session.save_recaptcha_token('browser-token')
    token_path = tmp_path / 'recaptcha_token.txt'
    assert stat.S_IMODE(token_path.stat().st_mode) == 0o600
    assert token_path.read_text() == 'browser-token'
    assert not list(tmp_path.glob('.*.tmp'))


@pytest.mark.parametrize('name', ['../escape', 'a/b', '.', '..', 'work account', ''])
def test_every_profile_operation_rejects_unsafe_names(tmp_path, name):
    manager = ProfileManager(str(tmp_path))
    with pytest.raises(ValueError, match='Invalid profile name'):
        manager.get_session(name)
    with pytest.raises(ValueError, match='Invalid profile name'):
        manager.remove_profile(name)
```

Add a symlink test that points a profile name outside the root and asserts deletion is rejected without touching the target.

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_08_session_security.py -q`

Expected: FAIL because writes use `Path.write_text()` directly and lookup/removal do not validate every profile name.

- [ ] **Step 3: Implement the storage boundary**

Core contract:

```python
PROFILE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*$')


def validate_profile_name(name: str) -> str:
    if not PROFILE_RE.fullmatch(name):
        raise ValueError(
            f"Invalid profile name '{name}'. Use alphanumeric characters, hyphens, or underscores."
        )
    return name


def direct_child(root: Path, name: str) -> Path:
    safe_name = validate_profile_name(name)
    candidate = root.resolve() / safe_name
    if candidate.parent != root.resolve():
        raise ValueError(f"Invalid profile name '{name}'.")
    return candidate
```

`atomic_write_text()` must create a sibling temporary file with `O_CREAT|O_EXCL`, write and `fsync`, apply `0600` on POSIX, then `os.replace()`. It must clean up its own temporary file on failure and refuse symlink cycles. Use it for session metadata, storage state, token, and global profile config.

Before `shutil.rmtree`, resolve both the profile path and profile root and require the target's parent to equal the resolved profile root. Reject symlinks instead of following them.

- [ ] **Step 4: Run targeted and existing business tests**

Run: `.venv/bin/python -m pytest tests/test_08_session_security.py tests/test_03_business_logic.py -q`

Expected: PASS with no files created outside `tmp_path`.

- [ ] **Step 5: Commit conditionally**

```bash
git add genspark_cli/storage.py genspark_cli/session.py genspark_cli/profiles.py tests/test_08_session_security.py
git commit -m "security: harden browser session storage"
```

Skip only when Git remains invalid.

---

### Task 3: Restore browser login and bounded token refresh

**Files:**
- Create: `genspark_cli/auth.py`
- Create: `tests/test_09_auth.py`
- Modify: `genspark_cli/cli.py`

**Interfaces:**
- Produces: `CapturedBrowserSession(storage_state: dict[str, Any], recaptcha_token: str)`.
- Produces: `BrowserLoginAdapter.capture(existing_state: dict | None, headless: bool) -> CapturedBrowserSession`.
- Produces: `async login_with_adapter(session: SessionManager, adapter: BrowserLoginAdapter, headless: bool) -> bool`.
- Produces: `run_login(session: SessionManager) -> bool`.
- Produces: `async _refresh_recaptcha_token(session: SessionManager) -> str | None`.

- [ ] **Step 1: Write failing adapter orchestration tests**

```python
class FakeAdapter:
    async def capture(self, existing_state, headless):
        assert existing_state is None
        assert headless is False
        return CapturedBrowserSession(
            storage_state={'cookies': [{'name': 'ai_session', 'value': 'cookie'}]},
            recaptcha_token='browser-recaptcha',
        )


@pytest.mark.asyncio
async def test_login_persists_only_browser_session_material(tmp_path):
    session = SessionManager(str(tmp_path))
    assert await login_with_adapter(session, FakeAdapter(), headless=False)
    assert session.get_cookies_dict()['ai_session'] == 'cookie'
    assert session.get_recaptcha_token() == 'browser-recaptcha'
    combined = ''.join(path.read_text() for path in tmp_path.glob('*') if path.is_file())
    assert 'api_key' not in combined.lower()
```

Add tests for empty token, adapter exception, existing storage-state pass-through, and refresh returning `None` after one failed capture.

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/python -m pytest tests/test_09_auth.py -q`

Expected: collection FAIL because `genspark_cli.auth` does not exist.

- [ ] **Step 3: Implement the adapter seam and Playwright adapter**

The Playwright adapter must:

- Lazy-import `playwright.async_api` so non-browser CLI commands still import without the extra.
- Launch Chromium headed unless `GENSPARK_HEADLESS=true` or refresh explicitly requests headless.
- Load existing storage state when present.
- Listen for requests to `/api/agent/ask_proxy`; parse `request.post_data_json`; capture only the non-empty `g_recaptcha_token`.
- Navigate to `https://www.genspark.ai/`, wait up to a documented timeout for an authenticated request, then save `context.storage_state()`.
- Never log request bodies, cookies, storage state, or tokens.
- Raise a typed `AuthenticationError` with the exact browser-install guidance when Playwright/Chromium is absent.

`_refresh_recaptcha_token()` uses saved storage state and exactly one adapter capture call. `run_login()` wraps `asyncio.run(login_with_adapter(...))` and preserves the current Boolean contract used by `cli.py`.

- [ ] **Step 4: Run auth and security tests**

Run: `.venv/bin/python -m pytest tests/test_09_auth.py tests/test_08_session_security.py -q`

Expected: PASS without launching a real browser.

- [ ] **Step 5: Commit conditionally**

```bash
git add genspark_cli/auth.py genspark_cli/cli.py tests/test_09_auth.py
git commit -m "feat: restore browser-token login"
```

---

### Task 4: Restore the shared browser-token chat client

**Files:**
- Create: `genspark_cli/client.py`
- Create: `tests/test_10_client.py`
- Modify: `genspark_cli/image_client.py`

**Interfaces:**
- Produces: `build_chat_payload(prompt: str, model: str, project_id: str | None, recaptcha_token: str, message_id: str | None = None) -> dict`.
- Produces: `GensparkClient(session: SessionManager, model: str = DEFAULT_MODEL, timeout: float = 180.0)`.
- Produces: `async GensparkClient.chat_stream(prompt: str, model: str | None = None) -> AsyncIterator[ChatChunk]`.
- Produces: `async GensparkClient.chat(prompt: str, model: str | None = None) -> ChatResponse`.
- Produces: `run_chat(session: SessionManager, prompt: str, model: str, stream: bool = False) -> ChatResponse`.
- Consumes: `parse_sse_line`, `ChatChunk`, `ChatResponse`, `SessionManager`, and `_refresh_recaptcha_token()`.

- [ ] **Step 1: Write failing payload and client tests**

```python
def test_chat_payload_contains_browser_token_and_conversation_state():
    payload = build_chat_payload(
        'hello', 'claude-opus-4-6', 'project-1', 'browser-token', message_id='msg-1'
    )
    assert payload['project_id'] == 'project-1'
    assert payload['messages'] == [{'role': 'user', 'id': 'msg-1', 'content': 'hello'}]
    assert payload['user_s_input'] == 'hello'
    assert payload['g_recaptcha_token'] == 'browser-token'
    assert payload['model_params']['model'] == 'claude-opus-4-6'
    assert 'api_key' not in json.dumps(payload).lower()


@pytest.mark.asyncio
async def test_chat_accumulates_sse_and_saves_project_id(session, mock_transport):
    client = GensparkClient(session, http_transport=mock_transport)
    result = await client.chat('hello')
    assert result.content == 'Hello world'
    assert result.project_id == 'project-2'
    assert session.last_project_id == 'project-2'
```

The synthetic response must include `project_start`, two `message_field/content` events, and `project_end`. Add tests for missing cookies, missing token, HTTP 401, 429, one refresh-and-retry, and no second refresh.

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/python -m pytest tests/test_10_client.py -q`

Expected: collection FAIL because `genspark_cli.client` does not exist.

- [ ] **Step 3: Implement the HTTP/SSE client**

Use the same `https://www.genspark.ai/api/agent/ask_proxy` endpoint, origin, referer, cookie source, and typed status mapping already used by `image_client.py`. The request builder keeps endpoint-specific fields in one function:

```python
return {
    'model_params': {'type': 'chat', 'model': model},
    'type': 'ai_chat_agent',
    'project_id': project_id,
    'messages': [message],
    'user_s_input': prompt,
    'writingContent': None,
    'use_moa_proxy': False,
    'ai_chat_enable_search': False,
    'g_recaptcha_token': recaptcha_token,
    'is_private': True,
    'push_token': '',
    'session_state': {'steps': [], 'messages': [message]},
}
```

Expose `http_transport` only as an injectable constructor test seam. `_ensure_client()` creates one `httpx.AsyncClient`; `close()`, `__aenter__`, and `__aexit__` manage it. `chat_stream()` parses each complete SSE data line and yields meaningful `ChatChunk` objects. `chat()` accumulates chunks into `ChatResponse`, then persists the observed project ID.

On `RecaptchaError`, call `_refresh_recaptcha_token()` once, reset the HTTP client so it reloads credentials, and retry once. Never recurse and never refresh on validation or generic 5xx errors.

- [ ] **Step 4: Reuse the same refresh bound in image generation**

Replace duplicated refresh flags in `image_client.py` with the same one-attempt control shape. Preserve its public constructor and generation methods.

- [ ] **Step 5: Run client, parser, image, and proxy tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_10_client.py tests/test_02_proxy_routes.py tests/test_06_image_models.py -q
```

Expected: PASS; no network requests occur.

- [ ] **Step 6: Commit conditionally**

```bash
git add genspark_cli/client.py genspark_cli/image_client.py tests/test_10_client.py
git commit -m "feat: restore browser-token chat client"
```

---

### Task 5: Restore MCP using the shared clients and router

**Files:**
- Create: `genspark_cli/mcp.py`
- Create: `tests/test_11_mcp.py`
- Modify: `tests/test_07_plugin_packaging.py`

**Interfaces:**
- Produces: `async _with_failover(operation, router: AccountRouter, preferred: str | None = None)`.
- Produces service functions: `chat`, `chat_with_context`, `get_models`, `check_status`, `generate_image`, and `list_image_models`.
- Produces: `create_mcp_server() -> FastMCP` and `run_mcp_server() -> None`.
- Consumes: `AccountRouter`, `GensparkClient`, `GensparkImageClient`, model registries, and browser-token sessions.

- [ ] **Step 1: Write failing MCP delegation tests**

```python
@pytest.mark.asyncio
async def test_chat_tool_uses_router_session_and_shared_client(fake_router):
    result = await chat('hello', model='claude-opus-4-6', router=fake_router,
                        client_factory=FakeChatClient)
    assert result['content'] == 'reply'
    assert result['profile'] == 'default'


def test_importing_mcp_module_does_not_require_mcp_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, 'mcp', None)
    module = importlib.reload(importlib.import_module('genspark_cli.mcp'))
    assert callable(module.run_mcp_server)
```

Add a failover test: first profile raises `RateLimitError`, router marks it unhealthy, second profile succeeds, and only two attempts occur.

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/python -m pytest tests/test_11_mcp.py -q`

Expected: collection FAIL because `genspark_cli.mcp` does not exist.

- [ ] **Step 3: Implement MCP service functions and lazy registration**

Keep service functions independent of FastMCP and dependency-inject router/client factories for tests. `create_mcp_server()` performs the lazy `from mcp.server.fastmcp import FastMCP`, constructs with `instructions=...`, and registers all six tools. If the extra is absent, raise one actionable error: `Install MCP support with: pip install -e '.[mcp]'`.

`_with_failover()` catches only `RateLimitError`, `SessionExpiredError`, and `RecaptchaError`; it marks the selected profile unhealthy, tries the next available profile, and never catches programming errors.

- [ ] **Step 4: Run MCP and packaging tests**

Run: `.venv/bin/python -m pytest tests/test_11_mcp.py tests/test_07_plugin_packaging.py -q`

Expected: PASS and `importlib.util.find_spec('genspark_cli.mcp')` resolves.

- [ ] **Step 5: Commit conditionally**

```bash
git add genspark_cli/mcp.py tests/test_11_mcp.py tests/test_07_plugin_packaging.py
git commit -m "feat: restore shared MCP server"
```

---

### Task 6: Add agent-native capabilities, doctor, and output contracts

**Files:**
- Create: `genspark_cli/capabilities.py`
- Create: `genspark_cli/doctor.py`
- Create: `tests/test_12_cli_contracts.py`
- Modify: `genspark_cli/cli.py`
- Modify: `genspark_cli/log.py`

**Interfaces:**
- Produces: `list_capabilities() -> list[dict[str, Any]]`.
- Produces: `run_doctor(session_dir: str | None = None) -> dict[str, Any]`.
- Produces Click commands `genspark capabilities [--json]` and `genspark doctor [--json]`.
- Consumes: installed module discovery, executable lookup, plugin paths, and profile health; it does not make Genspark network calls.

- [ ] **Step 1: Write failing CLI contract tests**

```python
def test_capabilities_json_is_clean_stdout():
    result = CliRunner().invoke(main, ['capabilities', '--json'])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert {item['id'] for item in payload['capabilities']} >= {'chat', 'image', 'mcp', 'openai-proxy'}
    assert 'browser_session' in {item['authentication'] for item in payload['capabilities']}


def test_doctor_reports_missing_login_without_failing_json(tmp_path):
    result = CliRunner().invoke(main, ['doctor', '--json'],
                                env={'GENSPARK_SESSION_DIR': str(tmp_path)})
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload['status'] == 'degraded'
    assert payload['checks']['browser_session']['status'] == 'missing'
```

Add a test that forces a command error in JSON mode and asserts valid error JSON on stdout, diagnostic detail on stderr, and non-zero exit code.

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/python -m pytest tests/test_12_cli_contracts.py -q`

Expected: FAIL because commands and registries do not exist.

- [ ] **Step 3: Implement deterministic local capability registry**

Each record has exact keys `id`, `description`, `authentication`, `entrypoints`, and `available`. Report only locally implemented features. Do not fetch official Tool API schemas and do not advertise connectors.

- [ ] **Step 4: Implement offline doctor checks**

Checks: Python version, core imports, Playwright module, Chromium executable, MCP module, plugin manifest, MCP manifest, CLI entrypoints, profile count, and browser-session health. Overall status is:

- `ok`: every required check passes and at least one browser session is fresh/aging.
- `degraded`: core/plugin checks pass but login or optional extras are missing.
- `error`: a required runtime, manifest, or entrypoint is missing.

Keep doctor exit code zero for `degraded`, non-zero for `error`.

- [ ] **Step 5: Separate stdout and stderr**

Construct the Rich console for human diagnostics with `Console(stderr=True)`. For JSON modes use only `click.echo(json.dumps(...))`. Ensure error envelopes set a non-zero Click exit without placing Rich markup before JSON.

- [ ] **Step 6: Run CLI and existing command tests**

Run: `.venv/bin/python -m pytest tests/test_12_cli_contracts.py tests/test_01_syntax_safety.py -q`

Expected: PASS.

- [ ] **Step 7: Commit conditionally**

```bash
git add genspark_cli/capabilities.py genspark_cli/doctor.py genspark_cli/cli.py genspark_cli/log.py tests/test_12_cli_contracts.py
git commit -m "feat: add agent-native CLI diagnostics"
```

---

### Task 7: Make installation, skills, and documentation truthful and repeatable

**Files:**
- Create: `tests/test_13_installation.py`
- Create: `skills/gen-setup/SKILL.md`
- Create: `skills/gen-chat/SKILL.md`
- Create: `skills/gen-imagegen/SKILL.md`
- Modify: `scripts/install.sh`
- Modify: `README.md`
- Modify: `requirements.txt`
- Remove: `skills/gen-setup.md`, `skills/gen-chat.md`, `skills/gen-imagegen.md`

**Interfaces:**
- Produces: `./scripts/install.sh [--no-browser]` with deterministic `.venv` installation.
- Produces: three Codex-discoverable skills with valid YAML frontmatter.
- Consumes: `genspark doctor --json`, `genspark auth login`, and the MCP entrypoint.

- [ ] **Step 1: Write failing installation/layout tests**

```python
def test_skills_use_canonical_plugin_layout():
    expected = {'gen-setup', 'gen-chat', 'gen-imagegen'}
    found = {p.parent.name for p in Path('skills').glob('*/SKILL.md')}
    assert found == expected
    assert not list(Path('skills').glob('gen-*.md'))


def test_installer_is_non_destructive_and_uses_supported_extra():
    script = Path('scripts/install.sh').read_text()
    assert "'.[all]'" in script or '".[all]"' in script
    assert '.zshrc' not in script
    assert '.bashrc' not in script
    assert 'genspark doctor --json' in script
```

Add checks for `bash -n scripts/install.sh`, required skill frontmatter keys, and README links resolving to existing local files.

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/python -m pytest tests/test_13_installation.py -q`

Expected: FAIL because skills are flat, installer edits shell profiles, and local docs links are broken.

- [ ] **Step 3: Rewrite the installer safely**

Use `set -euo pipefail`, resolve the script's parent as the plugin root, create/reuse `.venv`, upgrade pip, install `.[all]` or `.[server,mcp]` with `--no-browser`, and install Chromium only for the browser path. Do not modify `PATH`, shell profiles, or third-party MCP JSON. Print the absolute executables and explicit registration examples, then run `.venv/bin/genspark doctor --json`.

- [ ] **Step 4: Canonicalize the skills**

Move content into `skills/<name>/SKILL.md`, update commands to the verified surface, state that browser login is required, and remove claims about features not present in this workspace. The setup skill must merge MCP configuration rather than overwrite it and must not mutate configuration unless the user explicitly asks.

- [ ] **Step 5: Rewrite README around verified behavior**

Document:

- One-command local install.
- Manual development install.
- Browser-token architecture and local credential locations.
- `genspark`/`gsk`, `doctor`, `capabilities`, CLI chat/image, proxy, and MCP commands.
- Explicit disclaimer that this is an unofficial browser-session client and internal endpoints may change.
- Manual live smoke test instructions without exposing token contents.

Remove links to absent `docs/how-to-use.md` and `docs/9router-integration.md` unless those files are created with verified content.

- [ ] **Step 6: Run installation/layout tests and skill validation**

Run: `.venv/bin/python -m pytest tests/test_13_installation.py -q`

Expected: PASS.

Run each skill validator:

```bash
python3 /Users/todyle/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gen-setup
python3 /Users/todyle/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gen-chat
python3 /Users/todyle/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/gen-imagegen
```

Expected: all three pass.

- [ ] **Step 7: Commit conditionally**

```bash
git add scripts/install.sh README.md requirements.txt skills tests/test_13_installation.py
git commit -m "docs: make plugin installation agent-ready"
```

---

### Task 8: Expand the quality gate and prove an isolated installation

**Files:**
- Modify: `scripts/test_gate.sh`
- Modify: `.cm/CONTINUITY.md`
- Create: `.cm/handoff/quality.json`

**Interfaces:**
- Produces: one test gate that runs all `tests/test_*.py` files.
- Produces: isolated wheel-install evidence for all three console scripts.
- Consumes: all prior tasks and the canonical plugin validator.

- [ ] **Step 1: Write the gate expectation before editing the script**

Add to `tests/test_13_installation.py`:

```python
def test_gate_covers_every_test_module():
    script = Path('scripts/test_gate.sh').read_text()
    assert 'pytest tests -q' in script or 'python -m pytest tests -q' in script
    assert 'test_06_image_models.py' not in _excluded_test_names(script)
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/python -m pytest tests/test_13_installation.py::test_gate_covers_every_test_module -q`

Expected: FAIL because the current script enumerates only the first five test files.

- [ ] **Step 3: Simplify the complete test gate**

Activate `.venv` if present, resolve the repository root from the script location, run `python -m pytest tests -q`, run `python -m compileall -q genspark_cli`, and then run the plugin validator. Preserve non-zero exits and do not suppress warnings that indicate failures.

- [ ] **Step 4: Run the complete automated suite**

Run: `.venv/bin/python -m pytest tests -q`

Expected: every test passes, zero failures.

Run: `./scripts/test_gate.sh`

Expected: pytest, compileall, and plugin validation all pass.

- [ ] **Step 5: Build and install the wheel in an isolated temporary environment**

```bash
.venv/bin/python -m build
python3 -m venv /tmp/genspark-master-smoke-venv
/tmp/genspark-master-smoke-venv/bin/python -m pip install dist/genspark_cli-0.5.0-py3-none-any.whl
/tmp/genspark-master-smoke-venv/bin/genspark --help
/tmp/genspark-master-smoke-venv/bin/gsk --help
/tmp/genspark-master-smoke-venv/bin/genspark-mcp --help
/tmp/genspark-master-smoke-venv/bin/genspark doctor --json
```

Use a unique `mktemp -d` path during execution rather than the literal example path. Expected: all entrypoints resolve; doctor returns `degraded` only because no browser session/optional browser runtime exists in the isolated environment.

- [ ] **Step 6: Audit browser-token-only invariants**

Run:

```bash
rg -n "GSK_API_KEY|--api-key|api_key" genspark_cli pyproject.toml README.md skills
```

Expected: no authentication implementation or instructions introduce an API key. Mentions are permitted only in an explicit statement that API keys are unsupported; inspect each match manually.

Run the existing secret scan: `.venv/bin/python -m pytest tests/test_05_security_scan.py -q`.

- [ ] **Step 7: Write evidence handoff and continuity state**

`.cm/handoff/quality.json` records exact commands, exit codes, test counts, plugin validator result, wheel name, and manual live-test status. `.cm/CONTINUITY.md` sets Current Phase to `verified`, lists the browser-token-only decision, and distinguishes automated completion from the optional user-account smoke test.

- [ ] **Step 8: Final conditional commit**

```bash
git add scripts/test_gate.sh .cm/CONTINUITY.md .cm/handoff/quality.json
git commit -m "test: verify installable browser-token plugin"
```

If Git remains invalid, do not initialize it; report all changed files and verification evidence directly.

---

## Completion Checklist

- [ ] All ten acceptance criteria in the approved design map to passing evidence.
- [ ] Plugin validator passes on `/Volumes/Builder/Skills/genspark-master`.
- [ ] Full pytest and `scripts/test_gate.sh` pass.
- [ ] Wheel builds and all three entrypoints run in an isolated environment.
- [ ] Browser-token credential files are private and atomic on POSIX.
- [ ] Profile traversal/deletion containment tests pass.
- [ ] stdout/stderr JSON contracts pass.
- [ ] No API-key authentication path exists.
- [ ] README and three canonical skills match verified behavior.
- [ ] Live account smoke test is either completed with redacted evidence or explicitly handed to the user as the only external-account validation.

