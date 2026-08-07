---
name: gen-chat
description: Use the Genspark CLI for one-shot or interactive chat, model discovery, JSON output, conversations, and browser-profile failover. Use when the user asks to chat through Genspark, query a locally registered Genspark model, compare an answer, continue a conversation, or troubleshoot chat authentication. Requires a browser-authenticated Genspark session and does not use a Genspark API key.
---

# Chat through Genspark

## Check local readiness

Run:

```bash
genspark doctor --json
genspark auth status
```

If the browser session is missing or expired, ask the user to complete `genspark auth login`. Never print saved cookies or reCAPTCHA tokens.

## Discover and call

Inspect the local model registry instead of assuming a model is currently available upstream:

```bash
genspark models list --json
genspark chat ask "Explain the tradeoff" --json
genspark chat ask "Review this approach" --model claude-opus-4-6 --json
genspark chat ask "Stream this answer" --stream
```

Use `gsk` as an equivalent short alias when available. Use `genspark chat` for an interactive session and `genspark session list` for locally tracked conversations.

## Handle failures

- Missing or expired browser session: run `genspark auth login` or `genspark auth refresh <profile>`.
- Rate limit: allow bounded profile failover; optionally add another browser-authenticated profile with `genspark auth add <name>`.
- reCAPTCHA rejection: allow the single automatic refresh, then require headed login if it fails again.
- Network or upstream format error: report it without changing credentials or retrying indefinitely.

Treat all upstream model names and availability as changeable internal behavior.
