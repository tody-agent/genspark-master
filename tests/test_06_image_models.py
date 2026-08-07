"""Test suite for image models, styles, and configuration.

Validates image model registry, style categories, aspect ratios,
image sizes, and resolution functions are consistent and complete.
"""

import pytest


@pytest.mark.asyncio
async def test_image_refresh_budget_resets_for_each_generate_call(monkeypatch):
    """Each image request may refresh once without sharing another request's budget."""
    from genspark_cli.exceptions import RecaptchaError
    from genspark_cli.image_client import GensparkImageClient
    from genspark_cli.image_parser import ImageGenerationResult

    class StubSession:
        pass

    class RefreshingClient(GensparkImageClient):
        def __init__(self):
            super().__init__(StubSession())
            self.attempts = 0

        async def _generate_inner(self, *args, **kwargs):
            self.attempts += 1
            if self.attempts in {1, 3}:
                raise RecaptchaError("expired")
            return ImageGenerationResult(urls=["https://example.com/image.png"])

    refreshes = 0

    async def fake_refresh(_session):
        nonlocal refreshes
        refreshes += 1
        return "fresh-token"

    monkeypatch.setattr("genspark_cli.auth._refresh_recaptcha_token", fake_refresh)

    client = RefreshingClient()
    await client.generate("first")
    await client.generate("second")

    assert refreshes == 2


class TestImageModels:
    """Test image model registry."""

    def test_image_models_not_empty(self):
        from genspark_cli.image_models import IMAGE_MODELS
        assert len(IMAGE_MODELS) >= 7, f"Expected at least 7 image models, got {len(IMAGE_MODELS)}"

    def test_default_model_exists(self):
        from genspark_cli.image_models import IMAGE_MODELS, DEFAULT_IMAGE_MODEL
        assert DEFAULT_IMAGE_MODEL in IMAGE_MODELS, (
            f"Default model '{DEFAULT_IMAGE_MODEL}' not in registry"
        )

    def test_all_models_have_required_fields(self):
        from genspark_cli.image_models import IMAGE_MODELS
        for model_id, model in IMAGE_MODELS.items():
            assert model.id == model_id, f"Model ID mismatch: {model_id}"
            assert model.display_name, f"Model {model_id} missing display_name"
            assert model.provider, f"Model {model_id} missing provider"
            assert model.max_resolution, f"Model {model_id} missing max_resolution"

    def test_resolve_image_model_exact(self):
        from genspark_cli.image_models import resolve_image_model
        model = resolve_image_model("nano-banana-2")
        assert model.id == "nano-banana-2"

    def test_resolve_image_model_partial(self):
        from genspark_cli.image_models import resolve_image_model
        model = resolve_image_model("flux")
        assert "flux" in model.id

    def test_resolve_image_model_unknown(self):
        from genspark_cli.image_models import resolve_image_model
        with pytest.raises(ValueError, match="Unknown image model"):
            resolve_image_model("nonexistent-model-xyz")

    def test_list_image_models(self):
        from genspark_cli.image_models import list_image_models
        models = list_image_models()
        assert len(models) >= 7


class TestStyles:
    """Test style categories and resolution."""

    def test_style_categories_not_empty(self):
        from genspark_cli.image_models import STYLE_CATEGORIES
        assert len(STYLE_CATEGORIES) >= 10, (
            f"Expected at least 10 style categories, got {len(STYLE_CATEGORIES)}"
        )

    def test_all_styles_count(self):
        from genspark_cli.image_models import ALL_STYLES
        # 170+ styles + Auto Style
        assert len(ALL_STYLES) >= 170, (
            f"Expected at least 170 styles, got {len(ALL_STYLES)}"
        )

    def test_auto_style_first(self):
        from genspark_cli.image_models import ALL_STYLES
        assert ALL_STYLES[0] == "Auto Style"

    def test_no_duplicate_styles(self):
        from genspark_cli.image_models import ALL_STYLES
        # Auto Style is unique
        seen = set()
        duplicates = []
        for s in ALL_STYLES:
            if s in seen:
                duplicates.append(s)
            seen.add(s)
        # Allow known duplicates that exist in multiple categories
        # (e.g., "Minimalism" appears in both Modern Art and Graphic Design)
        assert len(duplicates) <= 3, f"Too many duplicate styles: {duplicates}"

    def test_resolve_style_auto(self):
        from genspark_cli.image_models import resolve_style
        assert resolve_style("auto") == "auto"
        assert resolve_style("") == "auto"
        assert resolve_style("Auto Style") == "auto"

    def test_resolve_style_exact(self):
        from genspark_cli.image_models import resolve_style
        assert resolve_style("Cyberpunk") == "Cyberpunk"
        assert resolve_style("Oil Painting") == "Oil Painting"

    def test_resolve_style_partial(self):
        from genspark_cli.image_models import resolve_style
        result = resolve_style("cyber")
        assert "Cyber" in result or "cyber" in result.lower()

    def test_resolve_style_case_insensitive(self):
        from genspark_cli.image_models import resolve_style
        assert resolve_style("cyberpunk") == "Cyberpunk"

    def test_resolve_style_unknown(self):
        from genspark_cli.image_models import resolve_style
        with pytest.raises(ValueError, match="Unknown style"):
            resolve_style("nonexistent-style-xyz-12345")

    def test_list_styles_all(self):
        from genspark_cli.image_models import list_styles
        result = list_styles()
        assert len(result) >= 10  # At least 10 categories

    def test_list_styles_search(self):
        from genspark_cli.image_models import list_styles
        result = list_styles(search="noir")
        # Should find Film Noir, Neo-Noir
        total = sum(len(v) for v in result.values())
        assert total >= 2, f"Expected at least 2 noir-related styles, got {total}"

    def test_list_styles_category(self):
        from genspark_cli.image_models import list_styles
        result = list_styles(category="Cinema")
        assert len(result) == 1  # One category matching "Cinema"


class TestAspectRatios:
    """Test aspect ratio validation."""

    def test_aspect_ratios_list(self):
        from genspark_cli.image_models import ASPECT_RATIOS
        assert len(ASPECT_RATIOS) == 14

    def test_resolve_ratio_auto(self):
        from genspark_cli.image_models import resolve_aspect_ratio
        assert resolve_aspect_ratio("auto") == "auto"
        assert resolve_aspect_ratio("") == "auto"

    def test_resolve_ratio_valid(self):
        from genspark_cli.image_models import resolve_aspect_ratio
        assert resolve_aspect_ratio("16:9") == "16:9"
        assert resolve_aspect_ratio("1:1") == "1:1"
        assert resolve_aspect_ratio("9:16") == "9:16"

    def test_resolve_ratio_invalid(self):
        from genspark_cli.image_models import resolve_aspect_ratio
        with pytest.raises(ValueError, match="Invalid aspect ratio"):
            resolve_aspect_ratio("99:1")


class TestImageSizes:
    """Test image size validation."""

    def test_image_sizes_list(self):
        from genspark_cli.image_models import IMAGE_SIZES
        assert IMAGE_SIZES == ["auto", "0.5K", "1K", "2K", "4K"]

    def test_resolve_size_auto(self):
        from genspark_cli.image_models import resolve_image_size
        assert resolve_image_size("auto") == "auto"
        assert resolve_image_size("") == "auto"

    def test_resolve_size_valid(self):
        from genspark_cli.image_models import resolve_image_size
        assert resolve_image_size("1K") == "1K"
        assert resolve_image_size("4K") == "4K"
        assert resolve_image_size("0.5K") == "0.5K"

    def test_resolve_size_numeric(self):
        from genspark_cli.image_models import resolve_image_size
        assert resolve_image_size("1024") == "1K"
        assert resolve_image_size("2048") == "2K"

    def test_resolve_size_invalid(self):
        from genspark_cli.image_models import resolve_image_size
        with pytest.raises(ValueError, match="Invalid image size"):
            resolve_image_size("8K")


class TestImageParser:
    """Test image SSE parser."""

    def test_extract_markdown_image_urls(self):
        from genspark_cli.image_parser import extract_image_urls
        text = '![cat](https://example.com/cat.png) and ![dog](https://example.com/dog.jpg)'
        urls = extract_image_urls(text)
        assert len(urls) == 2
        assert "cat.png" in urls[0]
        assert "dog.jpg" in urls[1]

    def test_extract_plain_urls(self):
        from genspark_cli.image_parser import extract_image_urls
        text = 'Here is the image: https://cdn.genspark.ai/output/123.png'
        urls = extract_image_urls(text)
        assert len(urls) >= 1

    def test_parse_sse_line_data(self):
        from genspark_cli.image_parser import parse_image_sse_line
        data = parse_image_sse_line('data: {"type": "project_start", "id": "abc123"}')
        assert data is not None
        assert data["type"] == "project_start"
        assert data["id"] == "abc123"

    def test_parse_sse_line_empty(self):
        from genspark_cli.image_parser import parse_image_sse_line
        assert parse_image_sse_line("") is None
        assert parse_image_sse_line(":comment") is None

    def test_parse_sse_done(self):
        from genspark_cli.image_parser import parse_image_sse_line
        data = parse_image_sse_line("data: [DONE]")
        assert data == {"type": "done"}

    def test_image_generation_result(self):
        from genspark_cli.image_parser import ImageGenerationResult
        result = ImageGenerationResult(urls=["https://example.com/img.png"])
        assert result.has_images
        assert result.primary_url == "https://example.com/img.png"

    def test_image_generation_result_empty(self):
        from genspark_cli.image_parser import ImageGenerationResult
        result = ImageGenerationResult()
        assert not result.has_images
        assert result.primary_url is None


class TestOpenAISizeMapping:
    """Test OpenAI size string to Genspark mapping in server.py."""

    def test_import_server_mapping(self):
        from genspark_cli.server import _openai_size_to_genspark
        assert _openai_size_to_genspark("auto") == ("auto", "auto")

    def test_standard_sizes(self):
        from genspark_cli.server import _openai_size_to_genspark
        ratio, size = _openai_size_to_genspark("1024x1024")
        assert ratio == "1:1"
        assert size == "1K"

    def test_wide_size(self):
        from genspark_cli.server import _openai_size_to_genspark
        ratio, size = _openai_size_to_genspark("1792x1024")
        assert ratio == "16:9"

    def test_tall_size(self):
        from genspark_cli.server import _openai_size_to_genspark
        ratio, size = _openai_size_to_genspark("1024x1792")
        assert ratio == "9:16"

    def test_ratio_passthrough(self):
        from genspark_cli.server import _openai_size_to_genspark
        ratio, size = _openai_size_to_genspark("16:9")
        assert ratio == "16:9"
        assert size == "auto"
