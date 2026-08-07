"""Image model registry for Genspark AI Image.

Maps image generation models, styles, aspect ratios, and sizes
to Genspark's internal API format.

Confirmed via browser inspection of genspark.ai/ai_image (Apr 2026).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ImageModelInfo:
    """Metadata for an image generation model on Genspark."""

    id: str                  # Internal Genspark ID sent in API requests
    display_name: str        # Human-readable name shown in UI
    provider: str            # Model provider
    max_resolution: str      # Maximum output resolution
    features: list[str] = field(default_factory=list)
    description: str = ""

    @property
    def cli_name(self) -> str:
        """Slug used in --model flag (lowercase, hyphens)."""
        return self.id


# ── Image Model Registry ─────────────────────────────────────────────────
# IDs confirmed from Genspark AI Image page (Apr 2026)

IMAGE_MODELS: dict[str, ImageModelInfo] = {
    "nano-banana-pro": ImageModelInfo(
        id="nano-banana-pro",
        display_name="Nano Banana Pro",
        provider="genspark",
        max_resolution="4K",
        features=["multi-image-input", "editing"],
        description="State-of-the-art generation and editing. Up to 14 images input, 2K/4K output.",
    ),
    "nano-banana-2": ImageModelInfo(
        id="nano-banana-2",
        display_name="Nano Banana 2",
        provider="google",
        max_resolution="4K",
        features=["multi-image-input", "fast", "reasoning"],
        description="Gemini 3.1 Flash Image. Fast with advanced reasoning, 0.5K/1K/2K/4K output.",
    ),
    "seedream-v5-lite": ImageModelInfo(
        id="seedream-v5-lite",
        display_name="Bytedance Seedream v5 Lite",
        provider="bytedance",
        max_resolution="3K",
        features=["multi-image-editing", "chinese-text", "fashion"],
        description="2K/3K resolution with multi-image editing. Excellent for Chinese text and fashion.",
    ),
    "flux-2": ImageModelInfo(
        id="flux-2",
        display_name="Flux 2",
        provider="black-forest-labs",
        max_resolution="2K",
        features=["realism", "crisp-text", "multi-image", "fast-editing"],
        description="Enhanced realism with crisp text. Fast editing and multi-image composition.",
    ),
    "flux-2-pro": ImageModelInfo(
        id="flux-2-pro",
        display_name="Flux 2 Pro",
        provider="black-forest-labs",
        max_resolution="4K",
        features=["premium", "realism"],
        description="Premium quality image generation with enhanced realism.",
    ),
    "z-image-turbo": ImageModelInfo(
        id="z-image-turbo",
        display_name="Z-Image Turbo",
        provider="genspark",
        max_resolution="2K",
        features=["fast", "turbo"],
        description="Ultra-fast image generation.",
    ),
    "gpt-image-2": ImageModelInfo(
        id="gpt-image-2",
        display_name="GPT Image 2",
        provider="openai",
        max_resolution="4K",
        features=["openai", "versatile", "text-rendering"],
        description="Latest GPT image model. Superior text rendering, editing, and face preservation.",
    ),
}

DEFAULT_IMAGE_MODEL = "nano-banana-2"


# ── Aspect Ratios ────────────────────────────────────────────────────────

ASPECT_RATIOS = [
    "auto", "21:9", "2:1", "16:9", "3:2", "4:3",
    "1:1", "3:4", "2:3", "9:16", "1:2", "9:21",
    "5:4", "4:5",
]

# ── Image Sizes ──────────────────────────────────────────────────────────

IMAGE_SIZES = ["auto", "0.5K", "1K", "2K", "4K"]


# ── Style Categories ─────────────────────────────────────────────────────

STYLE_CATEGORIES: dict[str, list[str]] = {
    "🎬 Cinema & Film": [
        "Film Noir", "Neo-Noir", "Crime Thriller", "Detective and Mystery",
        "Psychological Thriller", "Supernatural Horror", "Body Horror", "Slasher",
        "Science Fiction", "Hard Sci-Fi", "Space Opera", "Cyberpunk",
        "Post-Apocalyptic", "Dystopian", "Fantasy", "Dark Fantasy",
        "Epic Fantasy", "Historical Drama", "Period Piece", "War Film",
        "Western", "Action Blockbuster", "Spy and Espionage",
        "Romance", "Romantic Comedy", "Melodrama",
        "Coming-of-age", "Slice of Life", "Dark Comedy", "Satire",
    ],
    "📹 Documentary & Realism": [
        "Documentary", "Cinéma vérité", "Mockumentary", "Neorealism",
        "Expressionism (Film)", "Arthouse",
    ],
    "🎵 Commercial & Music": [
        "Music Video Aesthetic", "Commercial Advertising",
    ],
    "🎨 Color Grading": [
        "Teal and Orange Blockbuster", "Bleach Bypass", "Cross-Processed",
        "Film Print Emulation", "Kodak Warm Look", "Fuji Cool-Green Tone",
        "Golden Hour Warm", "Moonlight Blue", "Cyanotype-like Monoblue",
        "Matrix Green Cast", "Sepia", "Soft Pastel", "Muted Desaturated",
        "High Contrast Crisp", "Low Contrast Matte", "High-key Clean",
        "Low-key Moody", "Monochrome Black and White", "Monochrome Tinted",
        "Split Toning", "Vibrant Saturated", "Neon Night Grade",
        "Warm Shadows", "Cool Shadows",
    ],
    "📷 Lens & Effects": [
        "Clean Digital", "Light Film Grain", "Heavy Film Grain",
        "Halation", "Bloom", "Anamorphic Flare", "Vignetting",
        "Chromatic Aberration", "Lens Distortion", "Soft Focus",
        "Diffusion Filter Look", "Motion Blur", "Long Exposure Trails",
    ],
    "📼 Retro & Analog": [
        "CRT Scanlines", "VHS Tape", "DV Camcorder", "Hi8",
        "Polaroid", "Instant Film Frame", "Contact Sheet",
        "JPEG Artifacts", "Glitch", "Dust and Scratches", "Gate Weave",
    ],
    "📸 Photography": [
        "Portrait", "Beauty", "Headshot", "Fashion Editorial",
        "Street Style", "Street Photography", "Documentary Photojournalism",
        "Travel", "Landscape", "Cityscape", "Architecture", "Interior",
        "Product", "E-commerce Packshot", "Lifestyle Product", "Still Life",
        "Macro", "Wildlife", "Sports", "Event", "Wedding",
        "Automotive", "Aerial Drone", "Fine Art Photography",
    ],
    "🖼️ Fine Art (Classical)": [
        "Renaissance", "Baroque", "Rococo", "Neoclassicism",
        "Romanticism", "Realism", "Impressionism", "Post-Impressionism",
        "Symbolism", "Art Nouveau",
    ],
    "🎭 Modern Art": [
        "Fauvism", "Expressionism", "Cubism", "Futurism", "Dada",
        "Surrealism", "Constructivism", "Bauhaus",
        "Abstract Expressionism", "Minimalism", "Pop Art", "Op Art",
        "Contemporary Art",
    ],
    "🖌️ Traditional Media": [
        "Ukiyo-e", "Sumi-e Ink Wash", "Pencil Sketch", "Charcoal",
        "Ink Line Art", "Cross-hatching", "Watercolor", "Gouache",
        "Oil Painting", "Acrylic", "Pastel", "Marker",
        "Colored Pencil", "Graphite",
    ],
    "✂️ Printmaking & Craft": [
        "Etching", "Woodcut", "Linocut", "Screen Print",
        "Collage", "Paper Cut",
    ],
    "💻 Digital & Illustration": [
        "Flat Illustration", "Isometric Illustration", "Vector Illustration",
        "Pixel Art", "Comic Style", "Manga Style",
    ],
    "🔤 Graphic Design": [
        "Swiss International Typography", "Bauhaus Design", "Art Deco",
        "Art Nouveau Graphic", "Brutalism Graphic", "Minimalism",
        "Maximalism", "Corporate Clean", "Editorial Layout",
        "Typography-first Poster", "Geometric", "Memphis",
    ],
    "🌈 Aesthetic Movements": [
        "Vaporwave", "Synthwave", "Y2K", "Retro Vintage",
        "Punk Zine Collage", "Grunge",
    ],
    "🖥️ UI & Digital Design": [
        "Flat UI", "Skeuomorphism", "Glassmorphism", "Neumorphism",
        "Gradient Mesh", "Monoline", "Line Iconography", "Sticker Pack Style",
    ],
    "🎮 3D & Game Art": [
        "Photoreal CG", "Stylized 3D", "Animated Feature Look",
        "Claymation Look", "Plastic Toy Look", "Low Poly", "Voxel",
        "Pixel Art (Game)", "Cel Shading", "PBR Real-time Rendering",
        "Unreal Engine Look", "Octane Render Look", "Toon Render",
        "Isometric 3D", "Miniature Diorama", "Kitbash Concept Art",
        "Hand-painted Textures", "Anime 3D Game Look",
    ],
}

# Flat list for quick lookup
ALL_STYLES: list[str] = []
for _styles in STYLE_CATEGORIES.values():
    ALL_STYLES.extend(_styles)
# Add "Auto Style" as first entry
ALL_STYLES.insert(0, "Auto Style")


def resolve_image_model(name: str) -> ImageModelInfo:
    """Resolve an image model name to ImageModelInfo.

    Args:
        name: Model identifier — exact ID or partial match.

    Returns:
        ImageModelInfo for the resolved model.

    Raises:
        ValueError: If model name cannot be resolved.
    """
    # Exact match
    if name in IMAGE_MODELS:
        return IMAGE_MODELS[name]

    # Partial / fuzzy match
    name_lower = name.lower().replace(" ", "-").replace("_", "-")
    for model_id, info in IMAGE_MODELS.items():
        if name_lower in model_id or name_lower in info.display_name.lower():
            return info

    available = ", ".join(sorted(IMAGE_MODELS.keys()))
    raise ValueError(
        f"Unknown image model: '{name}'. Available models:\n  {available}"
    )


def list_image_models() -> list[ImageModelInfo]:
    """List all available image generation models."""
    return sorted(IMAGE_MODELS.values(), key=lambda m: (m.provider, m.id))


def list_styles(search: Optional[str] = None, category: Optional[str] = None) -> dict[str, list[str]]:
    """List styles, optionally filtered by search term or category.

    Args:
        search: Search term to filter styles (case-insensitive).
        category: Category name to filter.

    Returns:
        Dict of category → list of matching style names.
    """
    result: dict[str, list[str]] = {}

    for cat_name, styles in STYLE_CATEGORIES.items():
        if category and category.lower() not in cat_name.lower():
            continue

        if search:
            matching = [s for s in styles if search.lower() in s.lower()]
        else:
            matching = styles

        if matching:
            result[cat_name] = matching

    return result


def resolve_style(name: str) -> str:
    """Resolve a style name (case-insensitive, partial match).

    Returns the exact style name as used in the API.
    """
    if not name or name.lower() in ("auto", "auto style"):
        return "auto"

    name_lower = name.lower()

    # Exact match
    for style in ALL_STYLES:
        if style.lower() == name_lower:
            return style

    # Partial match
    for style in ALL_STYLES:
        if name_lower in style.lower():
            return style

    raise ValueError(
        f"Unknown style: '{name}'. Use 'genspark image styles' to see all available styles."
    )


def resolve_aspect_ratio(ratio: str) -> str:
    """Validate and normalize aspect ratio string."""
    if not ratio or ratio.lower() == "auto":
        return "auto"

    normalized = ratio.strip().replace(" ", "")
    if normalized in ASPECT_RATIOS:
        return normalized

    raise ValueError(
        f"Invalid aspect ratio: '{ratio}'. Available: {', '.join(ASPECT_RATIOS)}"
    )


def resolve_image_size(size: str) -> str:
    """Validate and normalize image size string."""
    if not size or size.lower() == "auto":
        return "auto"

    normalized = size.strip().upper()
    # Handle common variations
    size_map = {
        "0.5K": "0.5K", "512": "0.5K", "HALF": "0.5K",
        "1K": "1K", "1024": "1K",
        "2K": "2K", "2048": "2K",
        "4K": "4K", "4096": "4K",
    }

    if normalized in size_map:
        return size_map[normalized]

    raise ValueError(
        f"Invalid image size: '{size}'. Available: {', '.join(IMAGE_SIZES)}"
    )
