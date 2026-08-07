"""Model registry for Genspark AI Chat.

Maps human-friendly model names to Genspark internal IDs.
Confirmed via browser inspection of localStorage state.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelInfo:
    """Metadata for an AI model available on Genspark."""

    id: str                  # Internal Genspark ID sent in API requests
    display_name: str        # Human-readable name shown in UI
    provider: str            # Model provider (openai, anthropic, google, xai, meta)
    tier: str                # "premium", "fast", or "special"
    description: str = ""    # Short description
    reasoning: bool = False          # Supports reasoning mode
    context_window: int = 200000     # Max input tokens
    max_tokens: int = 32000          # Max output tokens

    @property
    def cli_name(self) -> str:
        """Slug used in --model flag (lowercase, hyphens)."""
        return self.id


# ── Model Registry ────────────────────────────────────────────────────────
# IDs confirmed from Genspark localStorage / ask_proxy payloads (May 2026)

MODELS: dict[str, ModelInfo] = {
    # ─── OpenAI ───
    "gpt-5.4": ModelInfo(
        id="gpt-5.4",
        display_name="GPT-5.4",
        provider="openai",
        tier="premium",
    ),
    "gpt-5.4-mini": ModelInfo(
        id="gpt-5.4-mini",
        display_name="GPT-5.4 Mini",
        provider="openai",
        tier="fast",
        max_tokens=16000,
    ),
    "gpt-5.4-nano": ModelInfo(
        id="gpt-5.4-nano",
        display_name="GPT-5.4 Nano",
        provider="openai",
        tier="fast",
        max_tokens=8000,
    ),
    "gpt-5.2-pro": ModelInfo(
        id="gpt-5.2-pro",
        display_name="GPT-5.2 Pro",
        provider="openai",
        tier="premium",
    ),
    "gpt-5.4-pro": ModelInfo(
        id="gpt-5.4-pro",
        display_name="GPT-5.4 Pro",
        provider="openai",
        tier="premium",
    ),
    "o3-pro": ModelInfo(
        id="o3-pro",
        display_name="o3-pro",
        provider="openai",
        tier="premium",
        description="OpenAI reasoning model",
        reasoning=True,
        max_tokens=100000,
    ),

    # ─── Anthropic ───
    "claude-opus-4-7": ModelInfo(
        id="claude-opus-4-7",
        display_name="Claude Opus 4.7",
        provider="anthropic",
        tier="ultra",
        description="Anthropic flagship — best reasoning, 1M context (Genspark Ultra)",
        context_window=1000000,
    ),
    "claude-opus-4-6": ModelInfo(
        id="claude-opus-4-6",
        display_name="Claude Opus 4.6",
        provider="anthropic",
        tier="premium",
    ),
    "claude-sonnet-4-6": ModelInfo(
        id="claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        provider="anthropic",
        tier="fast",
        max_tokens=16000,
    ),
    "claude-4-5-haiku": ModelInfo(
        id="claude-4-5-haiku",
        display_name="Claude Haiku 4.5",
        provider="anthropic",
        tier="fast",
        max_tokens=8000,
    ),

    # ─── Google ───
    "gemini-2.5-pro": ModelInfo(
        id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider="google",
        tier="premium",
        max_tokens=65000,
    ),
    "gemini-3-flash-preview": ModelInfo(
        id="gemini-3-flash-preview",
        display_name="Gemini 3 Flash Preview",
        provider="google",
        tier="fast",
        max_tokens=16000,
    ),
    "gemini-3.1-pro-preview": ModelInfo(
        id="gemini-3.1-pro-preview",
        display_name="Gemini 3.1 Pro Preview",
        provider="google",
        tier="premium",
        max_tokens=65000,
    ),

    # ─── xAI ───
    "grok-4.20-0309-non-reasoning": ModelInfo(
        id="grok-4.20-0309-non-reasoning",
        display_name="Grok 4.20",
        provider="xai",
        tier="premium",
    ),
    "grok-4.20-0309-reasoning": ModelInfo(
        id="grok-4.20-0309-reasoning",
        display_name="Grok 4.20 Reasoning",
        provider="xai",
        tier="premium",
        description="xAI reasoning model",
        reasoning=True,
        max_tokens=100000,
    ),
}

# Mixture-of-Agents uses a comma-separated list of model IDs
MOA_MODEL_IDS = "gpt-5.4-mini,claude-sonnet-4-6,gemini-3.1-pro-preview"

# Default model when none specified
DEFAULT_MODEL = "claude-opus-4-7"

# ── OpenAI-compatible name mapping ────────────────────────────────────────
# Maps OpenAI-style model names to Genspark IDs for the proxy server
OPENAI_TO_GENSPARK: dict[str, str] = {
    "gpt-4": "gpt-5.4",
    "gpt-4o": "gpt-5.4",
    "gpt-4o-mini": "gpt-5.4-mini",
    "gpt-4-turbo": "gpt-5.4-pro",
    "claude-3-opus": "claude-opus-4-7",
    "claude-4-opus": "claude-opus-4-7",
    "claude-opus": "claude-opus-4-7",
    "claude-3.5-sonnet": "claude-sonnet-4-6",
    "claude-3-haiku": "claude-4-5-haiku",
    "gemini-pro": "gemini-2.5-pro",
    "gemini-1.5-pro": "gemini-2.5-pro",
    "gemini-1.5-flash": "gemini-3-flash-preview",
}


def resolve_model(name: str) -> ModelInfo:
    """Resolve a model name (exact, alias, or OpenAI-compatible) to ModelInfo.

    Args:
        name: Model identifier — can be exact Genspark ID, OpenAI alias, or partial match.

    Returns:
        ModelInfo for the resolved model.

    Raises:
        ValueError: If model name cannot be resolved.
    """
    # Exact match
    if name in MODELS:
        return MODELS[name]

    # OpenAI alias
    if name in OPENAI_TO_GENSPARK:
        return MODELS[OPENAI_TO_GENSPARK[name]]

    # Partial / fuzzy match
    name_lower = name.lower().replace(" ", "-").replace("_", "-")
    for model_id, info in MODELS.items():
        if name_lower in model_id or name_lower in info.display_name.lower():
            return info

    available = ", ".join(sorted(MODELS.keys()))
    raise ValueError(
        f"Unknown model: '{name}'. Available models:\n  {available}"
    )


def to_openclaw_models() -> list[dict]:
    """Generate model definitions in OpenClaw provider format."""
    result = []
    for m in MODELS.values():
        entry = {
            "id": m.id,
            "name": m.display_name,
            "reasoning": m.reasoning,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": m.context_window,
            "maxTokens": m.max_tokens,
        }
        result.append(entry)
    return result


def to_openclaw_allowlist() -> dict[str, dict]:
    """Generate model allowlist entries for OpenClaw agents.defaults.models."""
    result = {}
    for m in MODELS.values():
        key = f"genspark/{m.id}"
        result[key] = {"alias": m.id}
    return result


def list_models(tier: Optional[str] = None, provider: Optional[str] = None) -> list[ModelInfo]:
    """List all available models, optionally filtered by tier or provider."""
    models = list(MODELS.values())
    if tier:
        models = [m for m in models if m.tier == tier]
    if provider:
        models = [m for m in models if m.provider == provider]
    return sorted(models, key=lambda m: (m.provider, m.tier, m.id))
