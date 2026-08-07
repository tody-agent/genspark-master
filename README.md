# Genspark Master

An unofficial, browser-session client and multi-agent skill suite for **Genspark** chat and image generation. It provides a Python CLI (`genspark` and `gsk`), six MCP tools, a local OpenAI-compatible proxy, and native global skills for **OpenAI Codex**, **Google Antigravity**, **Claude Code**, **OpenCode**, **Qwen**, and **Grok**.

Authentication uses cookies and a reCAPTCHA token captured from a headed Genspark browser session. This project does not accept or store a Genspark API key.

---

## ⚡ Quick Start & Installation

### 1. Local Repository Installation

Python 3.10+ is required. From this repository directory:

```bash
./scripts/install.sh
```

The installer creates or reuses `.venv`, installs browser/MCP/proxy support, installs Playwright Chromium, and runs the offline doctor.

To omit Playwright and Chromium (headless/pre-authenticated mode):

```bash
./scripts/install.sh --no-browser
```

### 2. Global CLI Symlinks

To use `genspark`, `gsk`, and `genspark-mcp` from any terminal directory:

```bash
ln -sf $(pwd)/.venv/bin/genspark ~/.local/bin/genspark
ln -sf $(pwd)/.venv/bin/gsk ~/.local/bin/gsk
ln -sf $(pwd)/.venv/bin/genspark-mcp ~/.local/bin/genspark-mcp
```

---

## 🌐 Global Skill Deployment for AI Agents

Genspark Master includes 3 production-grade agent skills:
- **`gen-chat`**: Chat, answer comparison, and model querying via Genspark.
- **`gen-imagegen`**: Image generation with style selection, custom aspect ratio, and resolution controls.
- **`gen-setup`**: Diagnostic, verification, and MCP setup.

To install these skills globally across all AI Agent environments on your system:

```bash
# Create target skill directories
mkdir -p ~/.gemini/config/skills \
         ~/.gemini/antigravity/skills \
         ~/.claude/skills \
         ~/.codex/skills \
         ~/.config/opencode/skills \
         ~/.qwen/skills \
         ~/.grok/skills

# Deploy skills globally
for skill in gen-chat gen-imagegen gen-setup; do
  cp -r ./skills/$skill ~/.gemini/config/skills/
  cp -r ./skills/$skill ~/.gemini/antigravity/skills/
  cp -r ./skills/$skill ~/.claude/skills/
  cp -r ./skills/$skill ~/.codex/skills/
  cp -r ./skills/$skill ~/.config/opencode/skills/
  cp -r ./skills/$skill ~/.qwen/skills/
  cp -r ./skills/$skill ~/.grok/skills/
done
```

---

## 🔌 MCP Server Registration (Multi-Agent Support)

Register `genspark-mcp` across your AI Agent configuration files.

### Standard `mcp.json` (Claude Code, OpenAI Codex, Google Antigravity)

Add to `~/.claude/mcp.json`, `~/.codex/mcp.json`, or `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "genspark": {
      "command": "/absolute/path/to/genspark-master/.venv/bin/genspark-mcp"
    }
  }
}
```

### OpenCode `opencode.json`

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "genspark": {
      "command": ["/absolute/path/to/genspark-master/.venv/bin/genspark-mcp"],
      "enabled": true,
      "type": "local"
    }
  }
}
```

---

## 🔐 Browser Authentication

Authenticate using a headed browser session:

```bash
genspark auth login
genspark auth status
```

1. Running `genspark auth login` opens a Playwright browser window.
2. Sign in to Genspark and send one chat message so the client captures the browser request token.
3. Subsequent chat/image requests use HTTP with the saved browser state. An expired token is refreshed automatically once per request when possible.

Credentials are stored locally under `~/.genspark/profiles/<profile>/` with private permissions:
- `storage_state.json`: Browser cookies and local storage.
- `recaptcha_token.txt`: Captured request token.
- `session.json`: Conversation metadata.

---

## 💡 Usage Guide

### Chat via CLI & Skills

```bash
# List available models
genspark models list --json

# Ask a prompt (JSON output)
genspark chat ask "Explain the trade-offs of microservices" --json

# Specify a target model using the gsk alias
gsk chat ask "Provide a second opinion" --model claude-opus-4-6

# Interactive chat session
genspark chat
```

### Image Generation

```bash
# List image models & styles
genspark image models --json
genspark image styles --search "watercolor" --json

# Generate and download image to current directory
genspark image generate "a peaceful mountain lake at sunrise"

# Advanced parameters
genspark image generate "editorial fashion portrait" \
  --model flux-2-pro \
  --style "Oil Painting" \
  --ratio 3:4 \
  --size 2K \
  --output ./downloads

# Generate without downloading (returns URL JSON)
genspark image generate "minimalist logo design" --no-download --json
```

### Local OpenAI-Compatible HTTP Proxy

Serve an OpenAI-compatible endpoint locally using your saved Genspark session:

```bash
genspark server start --host 127.0.0.1 --port 8080
```

Example request:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "messages": [{"role": "user", "content": "Hello Genspark Proxy"}]
  }'
```

---

## 🛠️ Diagnostics & Verification

Run offline machine-readable health checks:

```bash
genspark doctor --json
genspark capabilities --json
```

To run the complete test suite and package validation gate:

```bash
./scripts/test_gate.sh
```

---

## 📜 Disclaimer

This is an unofficial client relying on Genspark's browser flow and internal endpoints. Endpoints, model identifiers, availability, and rate limits can change without notice. Use only with accounts and data you are authorized to access.

## 📄 License

MIT
