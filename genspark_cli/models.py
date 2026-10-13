"""Model registry for Genspark AI Chat.

Maps human-friendly model names to Genspark internal IDs.
Updated with current Genspark AI Chat model lineup and credit multipliers.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelInfo:
    """Metadata for an AI model available on Genspark."""

    id: str                  # Internal Genspark ID sent in API requests
    display_name: str        # Human-readable name shown in UI
    provider: str            # Model provider (anthropic, openai, google, deepseek, etc.)
    tier: str                # "premium", "fast", or "ultra"
    multiplier: float = 1.0  # Credit multiplier (e.g. 4.0 for 4x)
    is_recommended: bool = False  # Recommended model in UI
    description: str = ""    # Short description
    reasoning: bool = False          # Supports reasoning mode
    context_window: int = 200000     # Max input tokens
    max_tokens: int = 32000          # Max output tokens

    @property
    def cli_name(self) -> str:
        """Slug used in --model flag (lowercase, hyphens)."""
        return self.id


# ── Model Registry ────────────────────────────────────────────────────────
# IDs and multipliers confirmed from Genspark Web UI

MODELS: dict[str, ModelInfo] = {
    # ─── Recommended Models ───
    "claude-opus-5.5": ModelInfo(
        id="claude-opus-5.5",
        display_name="Claude Opus 5.5",
        provider="anthropic",
        tier="ultra",
        multiplier=4.0,
        is_recommended=True,
        reasoning=True,
        context_window=1000000,
        description="Anthropic flagship Claude Opus 5.5 — best reasoning (Recommended, 4×)",
    ),
    "deepseek-v4.1-flash": ModelInfo(
        id="deepseek-v4.1-flash",
        display_name="DeepSeek V4.1 Flash",
        provider="deepseek",
        tier="fast",
        multiplier=0.3,
        is_recommended=True,
        description="DeepSeek V4.1 Flash high-efficiency (Recommended, 0.3×)",
    ),
    "glm-5.3-flash": ModelInfo(
        id="glm-5.3-flash",
        display_name="GLM-5.3 Flash",
        provider="zhipuai",
        tier="fast",
        multiplier=0.15,
        is_recommended=True,
        description="ZhipuAI GLM-5.3 Flash ultra-low cost (Recommended, 0.15×)",
    ),
    "gpt-6-sol": ModelInfo(
        id="gpt-6-sol",
        display_name="GPT-6 Sol",
        provider="openai",
        tier="premium",
        multiplier=2.0,
        is_recommended=True,
        description="OpenAI GPT-6 Sol flagship architecture (Recommended, 2×)",
    ),

    # ─── Anthropic ───
    "claude-opus-5": ModelInfo(
        id="claude-opus-5",
        display_name="Claude Opus 5",
        provider="anthropic",
        tier="ultra",
        multiplier=5.0,
        reasoning=True,
        context_window=1000000,
        description="Anthropic Claude 5 Opus (5×)",
    ),
    "claude-opus-4-8": ModelInfo(
        id="claude-opus-4-8",
        display_name="Claude Opus 4.8",
        provider="anthropic",
        tier="ultra",
        multiplier=5.0,
        reasoning=True,
        context_window=1000000,
        description="Anthropic Claude Opus 4.8 (5×)",
    ),
    "claude-opus-4-7": ModelInfo(
        id="claude-opus-4-7",
        display_name="Claude Opus 4.7",
        provider="anthropic",
        tier="ultra",
        multiplier=5.0,
        reasoning=True,
        context_window=1000000,
        description="Anthropic Claude Opus 4.7 (5×)",
    ),
    "claude-opus-4-6": ModelInfo(
        id="claude-opus-4-6",
        display_name="Claude Opus 4.6",
        provider="anthropic",
        tier="premium",
        multiplier=5.0,
        description="Claude Opus 4.6 high-capacity reasoning (5×)",
    ),
    "claude-sonnet-5.5": ModelInfo(
        id="claude-sonnet-5.5",
        display_name="Claude Sonnet 5.5",
        provider="anthropic",
        tier="premium",
        multiplier=2.0,
        description="Anthropic Claude Sonnet 5.5 (2×)",
    ),
    "claude-sonnet-5": ModelInfo(
        id="claude-sonnet-5",
        display_name="Claude Sonnet 5",
        provider="anthropic",
        tier="premium",
        multiplier=2.0,
        description="Next-gen Claude 5 Sonnet (2×)",
    ),
    "claude-sonnet-4-6": ModelInfo(
        id="claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        provider="anthropic",
        tier="fast",
        multiplier=3.0,
        max_tokens=16000,
        description="Claude Sonnet 4.6 (3×)",
    ),
    "claude-haiku-5.5": ModelInfo(
        id="claude-haiku-5.5",
        display_name="Claude Haiku 5.5",
        provider="anthropic",
        tier="fast",
        multiplier=0.1,
        max_tokens=8000,
        description="Claude Haiku 5.5 ultra-fast low-cost (0.1×)",
    ),
    "claude-haiku-4.5": ModelInfo(
        id="claude-haiku-4.5",
        display_name="Claude Haiku 4.5",
        provider="anthropic",
        tier="fast",
        multiplier=1.0,
        max_tokens=8000,
        description="Claude Haiku 4.5 (1×)",
    ),
    "claude-4-5-haiku": ModelInfo(
        id="claude-4-5-haiku",
        display_name="Claude Haiku 4.5",
        provider="anthropic",
        tier="fast",
        multiplier=1.0,
        max_tokens=8000,
        description="Claude Haiku 4.5 alias",
    ),

    # ─── OpenAI ───
    "gpt-6.1-sol": ModelInfo(
        id="gpt-6.1-sol",
        display_name="GPT-6.1 Sol",
        provider="openai",
        tier="premium",
        multiplier=2.0,
        description="OpenAI GPT-6.1 Sol (2×)",
    ),
    "gpt-6-luna": ModelInfo(
        id="gpt-6-luna",
        display_name="GPT-6 Luna",
        provider="openai",
        tier="fast",
        multiplier=0.1,
        description="OpenAI GPT-6 Luna low-cost (0.1×)",
    ),
    "gpt-5.6-sol": ModelInfo(
        id="gpt-5.6-sol",
        display_name="GPT-5.6 Sol",
        provider="openai",
        tier="premium",
        multiplier=4.0,
        description="Flagship OpenAI next-gen architecture (4×)",
    ),
    "gpt-5.6-terra": ModelInfo(
        id="gpt-5.6-terra",
        display_name="GPT-5.6 Terra",
        provider="openai",
        tier="premium",
        multiplier=2.0,
        description="OpenAI GPT-5.6 Terra (2×)",
    ),
    "gpt-5.6-luna": ModelInfo(
        id="gpt-5.6-luna",
        display_name="GPT-5.6 Luna",
        provider="openai",
        tier="fast",
        multiplier=0.2,
        description="OpenAI GPT-5.6 Luna (0.2×)",
    ),
    "gpt-5.5": ModelInfo(
        id="gpt-5.5",
        display_name="GPT-5.5",
        provider="openai",
        tier="premium",
        multiplier=5.0,
        description="OpenAI GPT-5.5 (5×)",
    ),
    "gpt-5.4": ModelInfo(
        id="gpt-5.4",
        display_name="GPT-5.4",
        provider="openai",
        tier="premium",
        multiplier=3.0,
        description="OpenAI GPT-5.4 (3×)",
    ),
    "gpt-5.4-mini": ModelInfo(
        id="gpt-5.4-mini",
        display_name="GPT-5.4 Mini",
        provider="openai",
        tier="fast",
        multiplier=1.0,
        max_tokens=16000,
        description="OpenAI GPT-5.4 Mini (1×)",
    ),
    "gpt-5.4-nano": ModelInfo(
        id="gpt-5.4-nano",
        display_name="GPT-5.4 Nano",
        provider="openai",
        tier="fast",
        multiplier=0.2,
        max_tokens=8000,
        description="OpenAI GPT-5.4 Nano (0.2×)",
    ),
    "gpt-5.4-pro": ModelInfo(
        id="gpt-5.4-pro",
        display_name="GPT-5.4 Pro",
        provider="openai",
        tier="premium",
        multiplier=3.0,
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

    # ─── Google ───
    "gemini-3.8-flash": ModelInfo(
        id="gemini-3.8-flash",
        display_name="Gemini 3.8 Flash",
        provider="google",
        tier="fast",
        multiplier=0.75,
        description="Google Gemini 3.8 Flash (0.75×)",
    ),
    "gemini-3.7-flash": ModelInfo(
        id="gemini-3.7-flash",
        display_name="Gemini 3.7 Flash",
        provider="google",
        tier="fast",
        multiplier=0.75,
        description="Google Gemini 3.7 Flash (0.75×)",
    ),
    "gemini-3.6-flash": ModelInfo(
        id="gemini-3.6-flash",
        display_name="Gemini 3.6 Flash",
        provider="google",
        tier="fast",
        multiplier=0.75,
        description="Google Gemini 3.6 Flash (0.75×)",
    ),
    "gemini-3.1-pro-preview": ModelInfo(
        id="gemini-3.1-pro-preview",
        display_name="Gemini 3.1 Pro Preview",
        provider="google",
        tier="premium",
        multiplier=2.0,
        max_tokens=65000,
        description="Google Gemini 3.1 Pro Preview (2×)",
    ),
    "gemini-3.1-flash-lite": ModelInfo(
        id="gemini-3.1-flash-lite",
        display_name="Gemini 3.1 Flash Lite",
        provider="google",
        tier="fast",
        multiplier=0.3,
        description="Google Gemini 3.1 Flash Lite (0.3×)",
    ),

    # ─── DeepSeek ───
    "deepseek-v4-pro": ModelInfo(
        id="deepseek-v4-pro",
        display_name="DeepSeek V4 Pro",
        provider="deepseek",
        tier="premium",
        multiplier=1.0,
        description="DeepSeek V4 Pro advanced reasoning",
    ),
    "deepseek-v4-flash": ModelInfo(
        id="deepseek-v4-flash",
        display_name="DeepSeek V4 Flash",
        provider="deepseek",
        tier="fast",
        multiplier=0.3,
    ),

    # ─── Kimi (Moonshot) ───
    "kimi-k3": ModelInfo(
        id="kimi-k3",
        display_name="Kimi K3",
        provider="kimi",
        tier="premium",
        multiplier=3.0,
        description="Moonshot Kimi K3 (3×)",
    ),

    # ─── MiniMax ───
    "minimax-m3": ModelInfo(
        id="minimax-m3",
        display_name="Minimax M3",
        provider="minimax",
        tier="fast",
        multiplier=0.3,
        description="MiniMax M3 (0.3×)",
    ),

    # ─── NVIDIA ───
    "nemotron-3-ultra": ModelInfo(
        id="nemotron-3-ultra",
        display_name="Nemotron 3 Ultra",
        provider="nvidia",
        tier="fast",
        multiplier=0.6,
        description="NVIDIA Nemotron 3 Ultra (0.6×)",
    ),

    # ─── xAI ───
    "grok-4.7": ModelInfo(
        id="grok-4.7",
        display_name="Grok 4.7",
        provider="xai",
        tier="premium",
        multiplier=2.0,
        description="xAI Grok 4.7 (2×)",
    ),
    "grok-4.6": ModelInfo(
        id="grok-4.6",
        display_name="Grok 4.6",
        provider="xai",
        tier="premium",
        multiplier=2.0,
        description="xAI Grok 4.6 (2×)",
    ),

    # ─── Xiaomi ───
    "mimo-v2.6-flash": ModelInfo(
        id="mimo-v2.6-flash",
        display_name="MiMo V2.6 Flash",
        provider="xiaomi",
        tier="fast",
        multiplier=0.14,
        description="Xiaomi MiMo V2.6 Flash (0.14×)",
    ),
    "mimo-v2.6-pro": ModelInfo(
        id="mimo-v2.6-pro",
        display_name="MiMo V2.6 Pro",
        provider="xiaomi",
        tier="fast",
        multiplier=0.435,
        description="Xiaomi MiMo V2.6 Pro (0.435×)",
    ),

    # ─── ZhipuAI ───
    "glm-5.3": ModelInfo(
        id="glm-5.3",
        display_name="GLM-5.3",
        provider="zhipuai",
        tier="premium",
        multiplier=1.0,
        description="ZhipuAI GLM-5.3 (1×)",
    ),
}

# Mixture-of-Agents default IDs
MOA_MODEL_IDS = "gpt-5.4-mini,claude-sonnet-4-6,gemini-3.1-pro-preview"

# Default model when none specified
DEFAULT_MODEL = "claude-opus-5.5"

# ── OpenAI-compatible name mapping ────────────────────────────────────────
# Maps OpenAI-style model names to Genspark IDs for the proxy server
OPENAI_TO_GENSPARK: dict[str, str] = {
    "gpt-4": "gpt-5.4",
    "gpt-4o": "gpt-5.4",
    "gpt-4o-mini": "gpt-5.4-mini",
    "gpt-4-turbo": "gpt-5.4-pro",
    "claude-3-opus": "claude-opus-5.5",
    "claude-4-opus": "claude-opus-5.5",
    "claude-opus": "claude-opus-5.5",
    "opus": "claude-opus-5.5",
    "opus-5.5": "claude-opus-5.5",
    "opus-5-5": "claude-opus-5.5",
    "claude-opus-5-5": "claude-opus-5.5",
    "claude-sonnet-5-5": "claude-sonnet-5.5",
    "claude-haiku-5-5": "claude-haiku-5.5",
    "claude-3.5-sonnet": "claude-sonnet-5.5",
    "claude-sonnet": "claude-sonnet-5.5",
    "claude-3-haiku": "claude-haiku-4.5",
    "gemini-pro": "gemini-3.1-pro-preview",
    "gemini-1.5-pro": "gemini-3.1-pro-preview",
    "gemini-1.5-flash": "gemini-3.8-flash",
    "gemini-flash": "gemini-3.8-flash",
    "deepseek": "deepseek-v4.1-flash",
    "deepseek-flash": "deepseek-v4.1-flash",
    "deepseek-v4-1-flash": "deepseek-v4.1-flash",
    "glm-5-3-flash": "glm-5.3-flash",
    "glm-5-3": "glm-5.3",
    "gpt-6-1-sol": "gpt-6.1-sol",
    "mimo-v2-6-flash": "mimo-v2.6-flash",
    "mimo-v2-6-pro": "mimo-v2.6-pro",
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
        target = OPENAI_TO_GENSPARK[name]
        if target in MODELS:
            return MODELS[target]

    # Normalized match (replace hyphens/underscores/dots)
    name_norm = name.lower().replace(" ", "-").replace("_", "-")
    for model_id, info in MODELS.items():
        if name_norm == model_id.lower().replace(" ", "-").replace("_", "-"):
            return info
        if name_norm.replace(".", "-") == model_id.lower().replace(".", "-"):
            return info

    # Partial / fuzzy match
    for model_id, info in MODELS.items():
        if name_norm in model_id.lower() or name_norm in info.display_name.lower().replace(" ", "-"):
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
    return sorted(models, key=lambda m: (not m.is_recommended, m.provider, m.multiplier, m.id))
