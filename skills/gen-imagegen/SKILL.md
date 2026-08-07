---
name: gen-imagegen
description: Generate and download images through the Genspark CLI using its local image-model and style registry. Use when a user asks for Genspark image generation, model/style discovery, aspect-ratio selection, JSON image output, or image-generation troubleshooting. Requires browser-session authentication and does not use a Genspark API key.
---

# Generate images through Genspark

## Verify and discover

Confirm the browser session without exposing its contents:

```bash
genspark doctor --json
genspark image models --json
genspark image styles --search "watercolor" --json
```

If login is missing, ask the user to run `genspark auth login` in the headed browser flow. Treat the local model registry as a compatibility map, not a guarantee of current upstream availability.

## Generate

Use explicit options only when the user requests them:

```bash
genspark image generate "a quiet coastal village at sunrise"
genspark image generate "editorial portrait" --model flux-2-pro --style "Oil Painting" --ratio 3:4 --size 2K
genspark image generate "minimal app icon" --no-download --json
```

Images download to the current directory by default. Use `--output <directory>` for a requested destination or `--no-download` when URLs alone are desired.

## Handle failures

- Missing/expired cookies or token: use `genspark auth login`.
- Rate limit or reCAPTCHA error: allow only bounded profile failover and one refresh per request.
- No returned image: report the upstream result; do not fabricate a local path.
- Download error: preserve returned URLs and report which files were not saved.
