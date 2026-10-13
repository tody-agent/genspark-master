---
name: gen-chat
description: Use the Genspark CLI for one-shot or interactive chat, model discovery, JSON output, conversations, and browser-profile failover. Use when the user asks to chat through Genspark, query a locally registered Genspark model, compare an answer, continue a conversation, or troubleshoot chat authentication. Requires a browser-authenticated Genspark session and does not use a Genspark API key.
---

# Chat through Genspark

Access leading AI Chat models — Anthropic Claude, OpenAI GPT-6/GPT-5, Google Gemini, DeepSeek, xAI Grok, Xiaomi MiMo, ZhipuAI GLM, and Moonshot Kimi — via Genspark browser session client.

## Prerequisites

Verify local session readiness without exposing credential tokens:

```bash
genspark doctor --json
genspark auth status
```

If login is missing or expired, ask the user to complete `genspark auth login` in the headed browser flow.

## Available Chat Models & Credit Multipliers

### 🔥 Recommended Models (Top Tier & High Efficiency)

| Model ID | Name | Provider | Tier | Multiplier | Reasoning | Context Window | Key Features / Best For |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `claude-opus-5.5` ★ | Claude Opus 5.5 | Anthropic | Ultra | 4.0× | **Yes** | 1,000,000 | **Default Model**. Flagship deep reasoning, code refactoring & UI/UX analysis. |
| `deepseek-v4.1-flash` 🔥 | DeepSeek V4.1 Flash | DeepSeek | Fast | 0.3× | No | 200,000 | Ultra-fast, high-efficiency logic & rapid prototyping. |
| `glm-5.3-flash` 🔥 | GLM-5.3 Flash | ZhipuAI | Fast | 0.15× | No | 200,000 | Extreme low-cost, high-speed drafting & parsing. |
| `gpt-6-sol` 🔥 | GPT-6 Sol | OpenAI | Premium | 2.0× | No | 200,000 | Next-generation OpenAI flagship architecture. |

### 🧠 Anthropic Claude Lineup

| Model ID | Name | Tier | Multiplier | Reasoning | Context Window | Key Features / Best For |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `claude-opus-5.5` ★ | Claude Opus 5.5 | Ultra | 4.0× | Yes | 1,000,000 | Flagship reasoning & architectural synthesis. |
| `claude-opus-5` | Claude Opus 5 | Ultra | 5.0× | Yes | 1,000,000 | Claude 5 Opus reasoning model. |
| `claude-opus-4-8` | Claude Opus 4.8 | Ultra | 5.0× | Yes | 1,000,000 | Claude Opus 4.8 reasoning model. |
| `claude-opus-4-7` | Claude Opus 4.7 | Ultra | 5.0× | Yes | 1,000,000 | Claude Opus 4.7 reasoning engine. |
| `claude-opus-4-6` | Claude Opus 4.6 | Premium | 5.0× | No | 200,000 | High-capacity reasoning & code review. |
| `claude-sonnet-5.5` | Claude Sonnet 5.5 | Premium | 2.0× | No | 200,000 | Balanced everyday tasks & UI design. |
| `claude-sonnet-5` | Claude Sonnet 5 | Premium | 2.0× | No | 200,000 | Next-gen Claude 5 Sonnet. |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 | Fast | 3.0× | No | 200,000 | Balanced everyday tasks. |
| `claude-haiku-5.5` | Claude Haiku 5.5 | Fast | 0.1× | No | 200,000 | Ultra-fast low-credit helper. |
| `claude-haiku-4.5` | Claude Haiku 4.5 | Fast | 1.0× | No | 200,000 | Low-latency lightweight execution. |

### ⚡ OpenAI Lineup

| Model ID | Name | Tier | Multiplier | Context Window | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gpt-6.1-sol` | GPT-6.1 Sol | Premium | 2.0× | 200,000 | Advanced GPT-6.1 logic. |
| `gpt-6-sol` 🔥 | GPT-6 Sol | Premium | 2.0× | 200,000 | OpenAI flagship architecture. |
| `gpt-6-luna` | GPT-6 Luna | Fast | 0.1× | 200,000 | Fast & ultra-efficient GPT-6. |
| `gpt-5.6-sol` | GPT-5.6 Sol | Premium | 4.0× | 200,000 | Heavy reasoning & synthesis. |
| `gpt-5.6-terra` | GPT-5.6 Terra | Premium | 2.0× | 200,000 | Balanced GPT-5.6 engine. |
| `gpt-5.6-luna` | GPT-5.6 Luna | Fast | 0.2× | 200,000 | Fast lightweight GPT-5.6. |
| `gpt-5.5` | GPT-5.5 | Premium | 5.0× | 200,000 | Premium GPT-5.5 model. |
| `gpt-5.4` | GPT-5.4 | Premium | 3.0× | 200,000 | Standard GPT-5.4 flagship. |
| `gpt-5.4-mini` | GPT-5.4 Mini | Fast | 1.0× | 200,000 | General code & text processing. |
| `gpt-5.4-nano` | GPT-5.4 Nano | Fast | 0.2× | 200,000 | Lightweight tasks. |

### 🌐 Google Gemini Lineup

| Model ID | Name | Tier | Multiplier | Context Window | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gemini-3.8-flash` | Gemini 3.8 Flash | Fast | 0.75× | 200,000 | Latest high-speed multimodal Flash. |
| `gemini-3.7-flash` | Gemini 3.7 Flash | Fast | 0.75× | 200,000 | Fast reasoning and coding. |
| `gemini-3.6-flash` | Gemini 3.6 Flash | Fast | 0.75× | 200,000 | Stable Flash generation. |
| `gemini-3.1-pro-preview` | Gemini 3.1 Pro Preview | Premium | 2.0× | 200,000 | Pro reasoning & long context. |
| `gemini-3.1-flash-lite` | Gemini 3.1 Flash Lite | Fast | 0.3× | 200,000 | Ultra-lightweight Google model. |

### 🚀 DeepSeek, ZhipuAI, Xiaomi, Kimi, NVIDIA, xAI & MiniMax

| Model ID | Name | Provider | Tier | Multiplier | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `deepseek-v4.1-flash` 🔥 | DeepSeek V4.1 Flash | DeepSeek | Fast | 0.3× | High-efficiency Chinese/English coding. |
| `glm-5.3-flash` 🔥 | GLM-5.3 Flash | ZhipuAI | Fast | 0.15× | Ultra-low cost fast inference. |
| `glm-5.3` | GLM-5.3 | ZhipuAI | Premium | 1.0× | Standard GLM bilingual model. |
| `mimo-v2.6-flash` | MiMo V2.6 Flash | Xiaomi | Fast | 0.14× | High-speed budget reasoning. |
| `mimo-v2.6-pro` | MiMo V2.6 Pro | Xiaomi | Fast | 0.435× | Xiaomi advanced Pro reasoning. |
| `kimi-k3` | Kimi K3 | Moonshot | Premium | 3.0× | Long-context Chinese research. |
| `minimax-m3` | Minimax M3 | MiniMax | Fast | 0.3× | Low-latency synthesis. |
| `nemotron-3-ultra` | Nemotron 3 Ultra | NVIDIA | Fast | 0.6× | Optimized system logic. |
| `grok-4.7` | Grok 4.7 | xAI | Premium | 2.0× | Real-time perspective & logic. |
| `grok-4.6` | Grok 4.6 | xAI | Premium | 2.0× | High-speed xAI reasoning. |

## Model Discovery & Execution

Always discover model availability dynamically via CLI:

```bash
# List all registered models with multipliers
genspark models list

# Output JSON format
genspark models list --json

# One-shot chat request with default model (Claude Opus 5.5)
genspark chat ask "Analyze this UX issue"

# Query specific model using CLI alias
genspark chat ask "Review this architecture" --model claude-opus-5.5
genspark chat ask "Rapid code generation" --model deepseek-v4.1-flash
genspark chat ask "Quick translation" --model glm-5.3-flash

# Stream chat response directly
genspark chat ask "Write a Python script for web scraping" --stream

# Interactive terminal session
genspark chat
```

## Session & History Management

```bash
# List tracked local sessions
genspark session list

# View active profile status
genspark auth status
```

## Error Handling

- **Credit exhaustion / Insufficient credits**: Switch to lower multiplier models (e.g. `deepseek-v4.1-flash` at 0.3× or `glm-5.3-flash` at 0.15×, `claude-haiku-5.5` at 0.1×).
- **Expired browser session**: Ask user to run `genspark auth login` or `genspark auth refresh <profile>`.
- **Rate limits**: Utilize bounded profile failover (`genspark auth add <name>`).
- **reCAPTCHA errors**: Allow automatic token refresh; request headed login if token refresh fails.
