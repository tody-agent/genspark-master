import pytest
from genspark_cli.models import MODELS, OPENAI_TO_GENSPARK, DEFAULT_MODEL, resolve_model

def test_models_config_sync():
    """
    Layer 4: Configuration Synchronization test.
    Ensures that internal model lists align with OPENAI compatibility dictionaries
    and that default behaviors are safely configured.
    """
    # 1. Ensure default model exists
    assert DEFAULT_MODEL in MODELS, "DEFAULT_MODEL not found in MODELS list"
    
    # 2. Assert some core models exist
    assert resolve_model("claude-opus-4-6").id == "claude-opus-4-6"
    assert resolve_model("gpt-5.4").id == "gpt-5.4"
    assert resolve_model("gemini-3.1-pro-preview").id == "gemini-3.1-pro-preview"

    # 3. Assert OpenAI aliases resolve correctly
    assert OPENAI_TO_GENSPARK["gpt-4o"] == "gpt-5.4"
    assert OPENAI_TO_GENSPARK["gpt-4-turbo"] == "gpt-5.4-pro"
    
    # 4. Resolve fallback model test
    with pytest.raises(ValueError) as exc:
        resolve_model("nonexistent-model")
    assert "Unknown model" in str(exc.value)
