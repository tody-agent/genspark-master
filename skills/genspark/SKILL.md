---
name: genspark
description: Master orchestrator skill for Genspark Multi-Account Pool, Parallel Batch Execution (`gsk batch` / `batch_chat` / `batch_generate_images`), Auto-Routing (`round-robin` + `least-busy` / `least-used` / `failover`), 32+ Flagship Chat Models, 7 Image Models, and Claude Code / Hermes style Agentic CLI (`gsk`). Use whenever the user mentions "genspark", "gsk", "đa tài khoản genspark", "chạy batch genspark", "xoay vòng tài khoản genspark", or wants to accelerate large coding, research, or media projects across multiple Genspark accounts concurrently.
---

# Genspark Master Orchestrator — Multi-Account Pool, Parallel Batch & Agentic CLI (`gsk`)

Genspark Master turns locally authenticated browser sessions (`~/.genspark/profiles/*/storage_state.json`) into a high-throughput, multi-account AI engine with **zero API keys**. It synchronizes routing state across all processes (`~/.genspark/router_state.json` via `fcntl.flock`) so `agy` CLI, MCP tools, and terminal commands share load seamlessly.

---

## 1. Quick Decision Matrix (Which Tool / Skill to Use)

| Goal / Scenario | Preferred MCP Tool (`genspark:*`) | Preferred CLI Command (`gsk`) | Dedicated Sub-Skill |
| :--- | :--- | :--- | :--- |
| **Single Chat / Second Opinion** | `genspark:chat` / `genspark:chat_with_context` | `gsk "Prompt" -m claude-opus-5.5` | `gen-chat` |
| **Large Project / Parallel Chat Batch** | `genspark:batch_chat` | `gsk batch "Task 1" "Task 2" -c 6` or `gsk batch -f tasks.jsonl -o out.jsonl -c 6` | `gen-chat` |
| **Single Image Generation (up to 4K)** | `genspark:generate_image` | `gsk -i "Prompt" -m flux-2-pro --size 2K` | `gen-imagegen` |
| **Parallel UI Concepts / Asset Batch** | `genspark:batch_generate_images` | `gsk batch --image "Concept A" "Concept B" "Concept C" -m flux-2-pro -o ./assets` | `gen-imagegen` |
| **Pool Health, Strategy & Cooldowns** | `genspark:configure_pool` / `genspark:check_status` | `gsk pool` / `gsk pool strategy round-robin` / `gsk pool reset` / `gsk pool ping` | `gen-setup` |
| **Interactive menu / onboarding / accounts** (human, TTY only) | — | `gsk` (menu) / `gsk setup` / `gsk accounts` / `gsk config -i` | `gen-setup` |
| **Scripted account ops** (agent-safe) | `genspark:configure_pool` | `gsk pool add|import|reset`, `gsk auth logout <name> -f` | `gen-setup` |

---

## 2. Exploiting Multi-Account Parallelism for Large Projects (Zero Waiting)

When tackling a large task (e.g., auditing 10 modules, generating 3–6 visual UI concepts, reviewing multiple PR diffs, or synthesizing multi-angle research), **never run sequential one-by-one requests** when multiple accounts or concurrency slots are available:

### A. Via MCP Tools (Inside `agy` CLI Agent Sessions)
1. **Check or tune pool strategy first (optional)**:
   - Call `genspark:configure_pool` with `{"strategy": "round-robin", "max_concurrency": 3}` (or `"reset_cooldowns": true` if accounts were previously rate-limited).
2. **Dispatch concurrent chat tasks (`genspark:batch_chat`)**:
   ```json
   {
     "prompts": [
       {"id": "auth-audit", "prompt": "Audit auth.py for race conditions", "model": "claude-opus-5.5"},
       {"id": "router-audit", "prompt": "Audit account_router.py for lock safety", "model": "gpt-6-sol"},
       {"id": "ux-copy", "prompt": "Draft microcopy for empty states", "model": "gemini-3.8-flash"}
     ],
     "concurrency": 6
   }
   ```
3. **Dispatch concurrent image generations (`genspark:batch_generate_images`)**:
   ```json
   {
     "prompts": [
       {"id": "concept-a", "prompt": "Apple Cupertino Daylight SaaS dashboard, #F5F5F7 background, pure white cards"},
       {"id": "concept-b", "prompt": "Xiaomi HyperOS Alive Bento workspace, #F7F8FA background, 20px rounded cards"},
       {"id": "concept-c", "prompt": "shadcn/ui New York Swiss hairline dashboard, #FFFFFF background, 1px zinc-200 border"}
     ],
     "model": "flux-2-pro",
     "aspect_ratio": "16:9",
     "image_size": "2K",
     "output_dir": "./concepts",
     "concurrency": 3
   }
   ```

### B. Via Terminal CLI (`gsk batch`)
```bash
# Inline parallel chat prompts
gsk batch "Analyze module A" "Analyze module B" "Analyze module C" -m claude-opus-5.5 -c 6 --json

# File-driven JSONL batch (ideal for 10–100+ tasks)
gsk batch --input-file tasks.jsonl --output results.jsonl --concurrency 8 --json

# Parallel image generation batch
gsk batch --image "Hero banner A" "Hero banner B" "Hero banner C" -m flux-2-pro --ratio 16:9 --output ./assets -c 3
```

---

## 3. Multi-Account Pool Management & Auto-Failover Rules

### Routing Strategies (`round-robin` | `least-used` | `failover`)
- **`round-robin` (Default — Smart Least-Busy)**: Rotates across all healthy accounts while prioritizing the account with the lowest active `in_flight` request count.
- **`least-used`**: Selects the healthy account with the lowest `(in_flight, total_requests)`.
- **`failover`**: Uses the primary/default account until it hits `max_concurrency` or enters cooldown, then spills over to backup accounts.

### Automatic Quota & Rate-Limit Failover
- When any account encounters `QuotaExhaustedError` (HTTP `402` or inline SSE credit-exhausted chunk), `RateLimitError` (HTTP `429`), `SessionExpiredError`, or `RecaptchaError`:
  1. `AccountRouter` records the cooldown in `~/.genspark/router_state.json` (`1800s` for quota exhaustion, `300s` for rate limits).
  2. The request **immediately fails over** to the next healthy account in the pool without losing progress.
- **Strict Model Integrity**: Never silently downgrades the requested model when all accounts are exhausted; instead, reports per-account status and remaining cooldown timer.

### Essential Pool & Config Commands
```bash
gsk pool                                      # Rich table of accounts, health, in-flight, and request stats
gsk pool add acc2 acc3                        # Login & add new accounts sequentially via browser
gsk pool import acc2 state.json --token "..." # Import Playwright storage_state.json headless
gsk pool strategy round-robin                 # Switch routing strategy
gsk pool ping                                 # Live concurrent health check across all accounts
gsk pool reset                                # Clear cooldown / quota_exhausted flags
gsk config -i                                 # Interactive step-by-step configuration wizard
```
