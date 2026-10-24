# Genspark Master AI Suite — Agent Operating Guidelines

## 🌟 Overview
Genspark Master is a zero-API-key AI gateway powered by a cross-process persistent pool of browser-authenticated sessions (`~/.genspark/profiles/*/storage_state.json` & `~/.genspark/router_state.json`). It exposes 32+ flagship chat models and 7 generative image models via an agentic CLI (`gsk` / `genspark`), stdio MCP server (`genspark-mcp`), and a local OpenAI-compatible HTTP proxy.

---

## 🧠 Supported AI Models

### 1. Flagship Chat Models
- `claude-opus-5.5` ★ / `claude-opus-4-7` / `claude-sonnet-5.5`: Complex reasoning, deep architectural design, and refactoring.
- `gpt-6-sol` / `gpt-6.1-sol` / `gpt-5.4`: Deep analytical problem-solving and algorithmic logic.
- `gemini-3.8-flash` / `gemini-3.1-pro-preview`: Multimodal synthesis, large context processing.
- `grok-4.7`: Real-time knowledge and fast code review.
- `deepseek-v4.1-flash` (`0.3×`) / `glm-5.3-flash` (`0.15×`): Ultra-fast, high-efficiency reasoning and code generation.

### 2. Generative Image Models
- `flux-2-pro`: Ultra-realistic photorealism, high-detail textures, and lighting.
- `nano-banana-2` ★: Fast stylized illustrations and visual mockups.
- `gpt-image-2`: High prompt adherence and typography in images.
- `seedream-v5-lite`: High-speed generation for rapid concept prototyping.

---

## 🛠️ Usage Protocols

### 1. MCP Tools (Preferred in Agent Sessions)
The plugin exposes the following stdio MCP tools under the `genspark` namespace:
- `genspark:chat`: Send a prompt to any supported chat model (with auto-failover across account pool).
- `genspark:chat_with_context`: Multi-turn dialogue with conversation context.
- `genspark:batch_chat`: Run multiple prompts concurrently in parallel across all healthy accounts in the pool.
- `genspark:generate_image`: Generate an image with chosen model, style, and aspect ratio.
- `genspark:batch_generate_images`: Generate multiple images concurrently across all healthy accounts in the pool.
- `genspark:configure_pool`: Inspect or update routing strategy (`round-robin`, `least-used`, `failover`), concurrency, and cooldowns.
- `genspark:get_models`: List available chat models.
- `genspark:check_status`: Check multi-account pool health state.
- `genspark:list_image_models`: Inspect image generation capabilities.

### 2. Agentic CLI Execution (`gsk` / `genspark`)
- `gsk`: Interactive numbered menu with first-run onboarding (humans only, needs a TTY); `gsk accounts` manages login/logout/add/remove. Agents must use scripted commands (`gsk pool ...`, `gsk auth logout <name> -f`) instead.
- `gsk "<prompt>" -m "<model>"`: Zero-friction one-shot query with multi-account failover.
- `gsk -i "<prompt>" --model "<model>" --output <path>`: Instant image generation.
- `gsk batch "Prompt 1" "Prompt 2" -c 4`: Parallel multi-account batch execution for large projects.
- `gsk pool` / `gsk pool ping` / `gsk pool add <name>`: Manage, test, and scale the multi-account pool.
- `gsk config`: View or update default models, routing strategy (`round-robin` / `least-used` / `failover`), and concurrency.
- `gsk doctor`: Verify session health, Playwright, and MCP status.

---

## 🔐 Authentication & Routing Guardrails
- **Strict Model Integrity**: When an account hits rate-limit or credit exhaustion, `AccountRouter` automatically fails over to the next healthy account in the pool without downgrading the requested model.
- **No API Keys**: If all accounts in the pool are expired or unauthenticated, do NOT ask for an API key. Guide the user to run `gsk auth login` or `gsk pool add <name>` in their terminal.
