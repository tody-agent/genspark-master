---
name: gen-imagegen
description: Generate and download images through the Genspark CLI (`gsk -i` / `gsk batch --image` / `genspark image generate`) and MCP (`generate_image` / `batch_generate_images`) using its multi-account pool and local image-model/style registry. Use when a user asks for single or parallel batch Genspark image generation, model/style discovery, aspect-ratio selection, or JSON output. Requires browser-session authentication and does not use a Genspark API key.
---

# Generate Images through Genspark (Single & Multi-Account Batch)

Free AI image generation powered by 7 top-tier models — Flux 2 Pro, GPT Image 2, Nano Banana Pro, Seedream v5 Lite, Z-Image Turbo, Nano Banana 2, and Flux 2. Features 170+ art styles, 14 aspect ratios, up to 4K resolution output, and concurrent multi-account batch execution.

## Prerequisites

Confirm the browser session and multi-account pool without exposing credential contents:

```bash
gsk doctor --json
gsk pool status
```

If login is missing or expired, ask the user to complete `gsk auth login` or add accounts with `gsk pool add <name>`.

## Available Image Models

| Model ID | Provider | Max Res | Best For / Key Features |
| :--- | :--- | :--- | :--- |
| `nano-banana-2` ★ | Google | 4K | **Default model**. Gemini 3.1 Flash Image. Fast generation with advanced reasoning. |
| `flux-2-pro` | Black Forest Labs | 4K | Premium quality, photorealism, fine details, cinematic lighting. |
| `gpt-image-2` | OpenAI | 4K | Superior text rendering, precise elements, face preservation. |
| `nano-banana-pro` | Genspark | 4K | SOTA generation & editing. Multi-image composition (up to 14 input images). |
| `seedream-v5-lite` | ByteDance | 3K | Multi-image editing, Chinese typography, fashion & portraiture. |
| `z-image-turbo` | Genspark | 2K | Ultra-fast generation. |
| `flux-2` | Black Forest Labs | 2K | Enhanced realism with crisp text and fast composition editing. |

## Discovery & Querying

Inspect available models and 170+ styles via CLI:

```bash
gsk image models --json
gsk image styles --search "watercolor" --json
```

## Generation Examples (Shorthand, Standard & Parallel Batch)

```bash
# Shorthand instant image generation (uses nano-banana-2 and multi-account failover)
gsk -i "a quiet coastal village at sunrise"

# Specify model, style, aspect ratio, resolution, and output directory
gsk image generate "editorial fashion portrait of a model" \
  --model flux-2-pro \
  --style "Oil Painting" \
  --ratio 3:4 \
  --size 2K \
  --output ./downloads

# Parallel Multi-Account Batch Image Generation (distributes across all accounts simultaneously)
gsk batch --image \
  "Concept A: Minimalist macOS dashboard in daylight" \
  "Concept B: Soft tactile Bento workspace" \
  "Concept C: Swiss hairline precision UI" \
  --model flux-2-pro --ratio 16:9 --size 2K --concurrency 3 --output ./concepts

# Generate without downloading (returns URL JSON)
gsk image generate "minimalist tech logo icon" --no-download --json
```

## Parameter Reference

- **`--model`**: One of the 7 supported model IDs (e.g. `flux-2-pro`, `gpt-image-2`, `nano-banana-2`).
- **`--style`**: Style name from `gsk image styles` (e.g. `"Cyberpunk"`, `"Oil Painting"`).
- **`--ratio`**: `auto`, `1:1`, `16:9`, `9:16`, `3:4`, `4:3`, `21:9`, `2:3`, `3:2`, `5:4`, `4:5`, `1:2`, `9:21`.
- **`--size`**: `auto`, `0.5K`, `1K`, `2K`, `4K`.
- **`--output`**: Directory where images should be saved (or `.json`/`.jsonl` file for `gsk batch --image`).
- **`--no-download`**: Output generated image URLs as JSON without saving files.

## Error Handling & Pool Failover

- **Rate limit / Quota exhausted / reCAPTCHA challenge**: Automatically marks the affected account in cooldown and retries on the next healthy account in the pool.
- **All accounts in cooldown**: Inspect with `gsk pool status`, reset with `gsk pool reset`, or add another account with `gsk pool add <name>`.
