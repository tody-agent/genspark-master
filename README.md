![Genspark Master AI Suite Banner](https://raw.githubusercontent.com/tody-agent/genspark-master/main/docs/assets/hero_banner.jpg)

# ✨ Genspark Master AI Suite

**The Ultimate Browser-Session AI Engine for Chat, Image Generation, MCP, and Multi-Agent Skills**

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/tody-agent/genspark-master/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-orange.svg)](#-mcp-server-registration-multi-agent-support)
[![15 Chat Models](https://img.shields.io/badge/Chat%20Models-15-cyan.svg)](#-supported-ai-models)
[![7 Image Models](https://img.shields.io/badge/Image%20Models-7-magenta.svg)](#-supported-ai-models)

---

## 🚀 Overview

**Genspark Master** turns your browser session into a high-performance, developer-first AI powerhouse. It provides a lightweight Python CLI (`genspark` and `gsk`), six production-grade MCP tools, a local OpenAI-compatible HTTP proxy server, and native global skills for **Google Antigravity**, **Claude Code**, **OpenAI Codex**, **OpenCode**, **Qwen**, and **Grok**.

No API keys needed — authenticates safely via a headed Genspark browser login.

---

## 🔥 Key Features

- 🔑 **Zero API Key Requirement**: Authenticates via browser session state (`storage_state.json` & reCAPTCHA token).
- 🧠 **15 Flagship Chat AI Models**: Claude Opus 4.7, GPT-5.4 Pro, o3-pro, Gemini 3.1 Pro, Grok 4.20, and more.
- 🎨 **7 Next-Gen Image Models**: Flux 2 Pro, GPT Image 2, Nano Banana 2, Seedream v5 Lite, Z-Image Turbo, up to 4K resolution & 170+ styles.
- 🤖 **Universal Multi-Agent Skills**: Pre-packaged skills (`gen-chat`, `gen-imagegen`, `gen-setup`) ready for all AI coding CLI tools.
- 🔌 **Built-in MCP Server**: Exposes 6 MCP tools for stdio clients (`chat`, `chat_with_context`, `generate_image`, `get_models`...).
- 🌐 **Local OpenAI HTTP Proxy**: Run `genspark server start` to expose `http://127.0.0.1:8080/v1/chat/completions` for any OpenAI-compatible app.

---

## 🎨 Image Generation Showcase

![Showcase of AI-Generated Artwork Styles](https://raw.githubusercontent.com/tody-agent/genspark-master/main/docs/assets/image_showcase.jpg)

*Generate 170+ artistic styles across 14 aspect ratios (`16:9`, `9:16`, `1:1`, `3:4`...) and resolution output up to 4K.*

---

## 🎯 Real-World Use Cases

### 💡 Use Case 1: Multi-Model Second Opinions & Code Reviews
Want a second opinion on a complex system architecture or code refactor? Query different SOTA reasoning engines instantly:
```bash
gsk chat ask "Analyze this deadlock condition in Python asyncio" --model claude-opus-4-7
gsk chat ask "Provide a second opinion on memory safety" --model o3-pro
```

### 🎨 Use Case 2: Free High-Res AI Art & Assets for Web Apps
Generate hero images, UI mockups, icons, and marketing assets directly from your terminal or AI Agent:
```bash
genspark image generate "editorial fashion portrait of a model in cyberpunk city" \
  --model flux-2-pro \
  --style "Oil Painting" \
  --ratio 3:4 \
  --size 2K \
  --output ./assets
```

### 🌐 Use Case 3: Local OpenAI API Bridge for Coding Assistants
Power Cursor, Continue, or custom scripts using your local Genspark proxy without paying per-token API fees:
```bash
# Start the local server
genspark server start --port 8080

# Call via standard OpenAI API client
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "gpt-5.4", "messages": [{"role": "user", "content": "Refactor this function"}]}'
```

### 🤖 Use Case 4: Autonomous Agent Execution (Antigravity, Codex, Claude Code)
When working with AI Agents, invoke `gen-chat` or `gen-imagegen` skills directly inside your conversation context:
```text
User: "/gen-imagegen create an isometric 3D icon for my banking app using Flux 2 Pro"
Agent: Executing Genspark CLI -> Tải ảnh 2K về thư mục dự án!
```

---

## 🤖 Supported AI Models

### 💬 Chat Models (15 SOTA Models)

| Model ID | Provider | Tier | Reasoning | Context Window | Key Strengths |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `claude-opus-4-7` ★ | **Anthropic** | Ultra | **Yes** | **1,000,000** | **Default**. Flagship reasoning & deep codebase analysis. |
| `claude-opus-4-6` | **Anthropic** | Premium | No | 200,000 | Deep logic analysis & code review. |
| `claude-sonnet-4-6` | **Anthropic** | Fast | No | 200,000 | Fast, balanced everyday tasks. |
| `claude-4-5-haiku` | **Anthropic** | Fast | No | 200,000 | Low-latency execution. |
| `gpt-5.4-pro` | **OpenAI** | Premium | No | 200,000 | Premium GPT-5.4 reasoning engine. |
| `gpt-5.4` | **OpenAI** | Premium | No | 200,000 | Standard GPT-5.4 flagship model. |
| `gpt-5.4-mini` | **OpenAI** | Fast | No | 200,000 | Fast general-purpose tier. |
| `gpt-5.4-nano` | **OpenAI** | Fast | No | 200,000 | Ultra-lightweight tier. |
| `gpt-5.2-pro` | **OpenAI** | Premium | No | 200,000 | Pro tier GPT-5.2 engine. |
| `o3-pro` | **OpenAI** | Premium | **Yes** | 200,000 | Deep step-by-step reasoning (100k output tokens). |
| `gemini-3.1-pro-preview` | **Google** | Premium | No | 200,000 | Advanced Google long-context reasoning. |
| `gemini-2.5-pro` | **Google** | Premium | No | 200,000 | Stable Google Pro model. |
| `gemini-3-flash-preview` | **Google** | Fast | No | 200,000 | Ultra-fast Google Flash model. |
| `grok-4.20-0309-reasoning` | **xAI** | Premium | **Yes** | 200,000 | xAI deep reasoning model (100k output tokens). |
| `grok-4.20-0309-non-reasoning` | **xAI** | Premium | No | 200,000 | High-performance xAI model. |

---

### 🎨 Image Generation Models (7 Next-Gen Engines)

| Model ID | Provider | Max Res | Best For / Key Features |
| :--- | :--- | :--- | :--- |
| `nano-banana-2` ★ | **Google** | **4K** | **Default**. Gemini 3.1 Flash Image. Fast generation with advanced reasoning. |
| `flux-2-pro` | **Black Forest Labs** | **4K** | Premium quality, photorealism, fine details, cinematic lighting. |
| `gpt-image-2` | **OpenAI** | **4K** | Superior text rendering, precise elements, face preservation. |
| `nano-banana-pro` | **Genspark** | **4K** | SOTA generation & editing. Multi-image composition (up to 14 input images). |
| `seedream-v5-lite` | **ByteDance** | **3K** | Multi-image editing, Chinese typography, fashion & portraiture. |
| `z-image-turbo` | **Genspark** | **2K** | Ultra-fast generation. |
| `flux-2` | **Black Forest Labs** | **2K** | Enhanced realism with crisp text and fast composition editing. |

---

## ⚡ Installation & Setup

### 1. Clone & Install Environment
Python 3.10+ is required:
```bash
git clone https://github.com/tody-agent/genspark-master.git
cd genspark-master
./scripts/install.sh
```

### 2. Global Executables Symlink
Symlink CLI executables into `~/.local/bin/` so you can run `genspark` or `gsk` from any shell folder:
```bash
ln -sf $(pwd)/.venv/bin/genspark ~/.local/bin/genspark
ln -sf $(pwd)/.venv/bin/gsk ~/.local/bin/gsk
ln -sf $(pwd)/.venv/bin/genspark-mcp ~/.local/bin/genspark-mcp
```

### 3. Deploy Multi-Agent Skills Globally
To make `gen-chat`, `gen-imagegen`, and `gen-setup` available to all AI agents on your machine:
```bash
mkdir -p ~/.gemini/config/skills \
         ~/.gemini/antigravity/skills \
         ~/.claude/skills \
         ~/.codex/skills \
         ~/.config/opencode/skills \
         ~/.qwen/skills \
         ~/.grok/skills

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

## 🔐 Authentication

Authenticate using a headed Playwright browser window:

```bash
genspark auth login
genspark auth status
```

1. Running `genspark auth login` opens a browser window.
2. Sign in to Genspark and send 1 chat message so the token is captured.
3. Credentials are saved locally with private permissions under `~/.genspark/profiles/<profile>/`.

---

## 🛠️ Diagnostics & Quality Gate

Run offline health checks:
```bash
genspark doctor --json
genspark capabilities --json
```

Run full test suite (106 unit tests + bytecode compilation + plugin check):
```bash
./scripts/test_gate.sh
```

---

## 📜 Disclaimer & License

*This is an unofficial browser-session client and skill suite. All model trademarks belong to their respective creators (OpenAI, Anthropic, Google, Black Forest Labs, ByteDance, xAI, Genspark).*

Released under the [MIT License](LICENSE).
