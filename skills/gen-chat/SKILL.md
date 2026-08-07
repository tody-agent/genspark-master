---
name: gen-chat
description: Use the Genspark CLI for one-shot or interactive chat, model discovery, JSON output, conversations, and browser-profile failover. Use when the user asks to chat through Genspark, query a locally registered Genspark model, compare an answer, continue a conversation, or troubleshoot chat authentication. Requires a browser-authenticated Genspark session and does not use a Genspark API key.
---

# Chat through Genspark

Access leading AI Chat models — Anthropic Claude, OpenAI GPT-5, Google Gemini, and xAI Grok — free via Genspark browser session client.

## Prerequisites

Verify local session readiness without exposing credential tokens:

```bash
genspark doctor --json
genspark auth status
```

If login is missing or expired, ask the user to complete `genspark auth login` in the headed browser flow.

## Available Chat Models

| Model ID | Provider | Tier | Reasoning | Context Window | Key Features / Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `claude-opus-4-7` ★ | Anthropic | Ultra | Yes | 1,000,000 | **Default Model**. Flagship reasoning & deep analysis. |
| `claude-opus-4-6` | Anthropic | Premium | No | 200,000 | High-capacity reasoning & code review. |
| `claude-sonnet-4-6` | Anthropic | Fast | No | 200,000 | Fast, balanced everyday tasks. |
| `claude-4-5-haiku` | Anthropic | Fast | No | 200,000 | Lightweight, low-latency execution. |
| `gpt-5.4-pro` | OpenAI | Premium | No | 200,000 | Premium GPT-5.4 logic and complex synthesis. |
| `gpt-5.4` | OpenAI | Premium | No | 200,000 | Standard GPT-5.4 flagship model. |
| `gpt-5.4-mini` | OpenAI | Fast | No | 200,000 | Fast GPT-5.4 tier for general code and text. |
| `gpt-5.4-nano` | OpenAI | Fast | No | 200,000 | Lightweight GPT-5.4 tier. |
| `gpt-5.2-pro` | OpenAI | Premium | No | 200,000 | Pro tier GPT-5.2 engine. |
| `o3-pro` | OpenAI | Premium | **Yes** | 200,000 | Deep step-by-step reasoning (100k max output tokens). |
| `gemini-3.1-pro-preview` | Google | Premium | No | 200,000 | Advanced Google reasoning & long context. |
| `gemini-2.5-pro` | Google | Premium | No | 200,000 | Stable Google Pro model. |
| `gemini-3-flash-preview` | Google | Fast | No | 200,000 | Ultra-fast Google Flash model. |
| `grok-4.20-0309-reasoning` | xAI | Premium | **Yes** | 200,000 | xAI deep reasoning model (100k max output tokens). |
| `grok-4.20-0309-non-reasoning` | xAI | Premium | No | 200,000 | High-performance xAI non-reasoning model. |

## Model Discovery & Execution

Always discover model availability dynamically via CLI:

```bash
# List all registered models
genspark models list --json

# One-shot chat request (JSON output)
genspark chat ask "Explain quantum computing principles" --json

# Query specific model using CLI alias
gsk chat ask "Review this architecture" --model gpt-5.4-pro

# Reasoning model query
genspark chat ask "Solve this math problem step-by-step" --model o3-pro

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

- **Expired browser session**: Ask user to run `genspark auth login` or `genspark auth refresh <profile>`.
- **Rate limits**: Utilize bounded profile failover (`genspark auth add <name>`).
- **reCAPTCHA errors**: Allow automatic token refresh; request headed login if token refresh fails.
- **Upstream error**: Report API result directly without retry loops or credential modification.
