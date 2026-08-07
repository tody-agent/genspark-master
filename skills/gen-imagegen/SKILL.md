---
name: gen-imagegen
description: Generate and download images through the Genspark CLI using its local image-model and style registry. Use when a user asks for Genspark image generation, model/style discovery, aspect-ratio selection, JSON image output, or image-generation troubleshooting. Requires browser-session authentication and does not use a Genspark API key.
---

# Generate images through Genspark

Free AI image generation powered by 7 top-tier models — Flux 2 Pro, GPT Image 2, Nano Banana Pro, Seedream v5 Lite, Z-Image Turbo, Nano Banana 2, and Flux 2. Features 170+ art styles, 14 aspect ratios, and up to 4K resolution output.

## Prerequisites

Confirm the browser session without exposing its contents:

```bash
genspark doctor --json
genspark auth status
```

If login is missing or expired, ask the user to complete `genspark auth login` in the headed browser flow.

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
genspark image models --json
genspark image styles --search "watercolor" --json
```

## Generation Examples

Use explicit parameters only when specified by the user:

```bash
# Default generation (uses nano-banana-2)
genspark image generate "a quiet coastal village at sunrise"

# Specify model, style, aspect ratio, resolution, and output directory
genspark image generate "editorial fashion portrait of a model" \
  --model flux-2-pro \
  --style "Oil Painting" \
  --ratio 3:4 \
  --size 2K \
  --output ./downloads

# Generate without downloading (returns URL JSON)
genspark image generate "minimalist tech logo icon" --no-download --json
```

## Parameter Reference

- **`--model`**: One of the 7 supported model IDs (e.g. `flux-2-pro`, `gpt-image-2`).
- **`--style`**: Style name from `genspark image styles` (e.g. `"Cyberpunk"`, `"Oil Painting"`).
- **`--ratio`**: `auto`, `1:1`, `16:9`, `9:16`, `3:4`, `4:3`, `21:9`, `2:3`, `3:2`, `5:4`, `4:5`, `1:2`, `9:21`.
- **`--size`**: `auto`, `0.5K`, `1K`, `2K`, `4K`.
- **`--output`**: Directory where images should be saved (defaults to current working directory).
- **`--no-download`**: Output generated image URLs as JSON without saving files.

## Error Handling

- **Missing/expired cookies or token**: Run `genspark auth login`.
- **Rate limit or reCAPTCHA error**: Allow automatic single refresh; prompt headed login if refresh fails.
- **Upstream error**: Report the result directly without fabricating image paths.
- **Download error**: Preserve returned URLs and report failed downloads clearly.
