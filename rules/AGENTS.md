# Genspark Master AI Suite — Agent Operating Guidelines

## 🌟 Overview
Genspark Master is a zero-API-key AI gateway powered by browser-authenticated sessions (`~/.genspark/storage_state.json`). It exposes 15 flagship chat models and 7 generative image models via CLI, stdio MCP server, and a local OpenAI-compatible HTTP proxy.

---

## 🧠 Supported AI Models

### 1. Flagship Chat Models
- `claude-opus-4.7` / `claude-sonnet-3.7`: Complex reasoning, deep architectural design, and refactoring.
- `gpt-5.4-pro` / `o3-pro`: Deep analytical problem-solving and algorithmic logic.
- `gemini-3.1-pro`: Multimodal synthesis, large context processing.
- `grok-4.20`: Real-time knowledge and fast code review.
- `deepseek-r1` / `deepseek-v3`: Cost-effective reasoning and code generation.

### 2. Generative Image Models
- `flux-2-pro`: Ultra-realistic photorealism, high-detail textures, and lighting.
- `nano-banana-2`: Fast stylized illustrations and visual mockups.
- `gpt-image-2`: High prompt adherence and typography in images.
- `seedream-v5-lite`: High-speed generation for rapid concept prototyping.

---

## 🛠️ Usage Protocols

### 1. MCP Tools (Preferred in Agent Sessions)
The plugin exposes the following stdio MCP tools under the `genspark` namespace:
- `genspark:chat`: Send a prompt to any supported chat model.
- `genspark:chat_with_context`: Multi-turn dialogue with conversation context.
- `genspark:generate_image`: Generate an image with chosen model, style, and aspect ratio.
- `genspark:get_models`: List available chat and image models with health state.
- `genspark:check_status`: Check browser session authentication status.
- `genspark:list_image_models`: Inspect image generation capabilities.

### 2. CLI Execution
- `genspark chat ask "<prompt>" --model "<model>"`: One-shot query.
- `genspark image create "<prompt>" --model "<model>" --output <path>`: Generate and save an image.
- `genspark doctor`: Verify session health, Playwright, and MCP status.
- `genspark auth login`: Initiate interactive browser login to refresh session cookies.

---

## 🔐 Authentication Guardrails
- If Genspark calls return `401 Unauthorized` or session invalid:
  - Do NOT attempt to ask for an API key (Genspark does not use API keys).
  - Guide the user to run `genspark auth login` in their terminal to refresh the browser session.
