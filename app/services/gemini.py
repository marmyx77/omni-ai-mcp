"""
Gemini AI Service

This module provides the core Gemini client and model configurations.
It handles client initialization, model mappings, and API calls with fallback.
"""

import os
from collections.abc import Mapping
from typing import Any, Dict, Iterator, Optional

from ..core import config, log_progress

# Model maps resolve lazily through the dynamic registry (v4.6.0): every
# lookup returns the newest matching model the API exposes, or the explicit
# GEMINI_MODEL_* override, or the static config fallback. Tools keep using
# MODELS.get(alias, MODELS["pro"]) exactly as before.
from .model_registry import model_registry


class _LazyModelMap(Mapping):
    """Read-only alias → model-ID map backed by the model registry."""

    def __init__(self, aliases: Dict[str, str]) -> None:
        self._aliases = dict(aliases)  # alias → registry category

    def __getitem__(self, alias: str) -> str:
        return model_registry.resolve(self._aliases[alias])

    def __iter__(self) -> Iterator[str]:
        return iter(self._aliases)

    def __len__(self) -> int:
        return len(self._aliases)

    def category(self, alias: str) -> str:
        """Registry category behind an alias (raises KeyError if unknown)."""
        return self._aliases[alias]


MODELS = _LazyModelMap({
    "pro": "text_pro",            # Best for reasoning, coding, complex tasks
    "flash": "text_flash",        # Balanced speed/quality for standard tasks
    "fast": "text_flash",         # High-volume, simple tasks (same as flash)
    "flash-lite": "text_flash_lite",
})

IMAGE_MODELS = _LazyModelMap({
    "pro": "image",               # High quality, 4K, thinking mode
    "flash": "image_flash",       # Fast generation
})

VIDEO_MODELS = _LazyModelMap({
    "veo31": "video",             # Best quality, 8s, 720p/1080p, audio
    "veo31_fast": "video_fast",   # Faster, optimized for speed
    "veo31_lite": "video_lite",   # Cheapest, 720p
})

TTS_MODELS = _LazyModelMap({
    "flash": "tts",               # Fast TTS
    "pro": "tts_pro",             # Higher quality TTS
})

TTS_VOICES = {
    "Zephyr": "Bright",
    "Puck": "Upbeat",
    "Charon": "Informative",
    "Kore": "Firm",
    "Fenrir": "Excitable",
    "Leda": "Youthful",
    "Orus": "Firm",
    "Aoede": "Breezy",
    "Callirrhoe": "Easy-going",
    "Autonoe": "Bright",
    "Enceladus": "Breathy",
    "Iapetus": "Clear",
    "Umbriel": "Easy-going",
    "Algieba": "Smooth",
    "Despina": "Smooth",
    "Erinome": "Clear",
    "Algenib": "Gravelly",
    "Rasalgethi": "Informative",
    "Laomedeia": "Upbeat",
    "Achernar": "Soft",
    "Alnilam": "Firm",
    "Schedar": "Even",
    "Gacrux": "Mature",
    "Pulcherrima": "Forward",
    "Achird": "Friendly",
    "Zubenelgenubi": "Casual",
    "Vindemiatrix": "Gentle",
    "Sadachbia": "Lively",
    "Sadaltager": "Knowledgeable",
    "Sulafat": "Warm",
}

# Client initialization
client = None
types = None
_error: Optional[str] = None
_available: bool = False

try:
    from google import genai
    from google.genai import types as genai_types

    types = genai_types

    API_KEY = config.api_key
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        _error = "Please set GEMINI_API_KEY environment variable"
    else:
        client = genai.Client(api_key=API_KEY)
        _available = True
except ImportError:
    _error = "google-genai SDK not installed. Run: pip install google-genai"
except Exception:
    _error = "Failed to initialize Gemini client. Check your API key."


def is_available() -> bool:
    """Check if Gemini client is available."""
    return _available


def get_error() -> Optional[str]:
    """Get initialization error message if any."""
    return _error


def generate_with_fallback(
    model_id: str,
    contents: Any,
    config: Any = None,
    operation: str = "request"
) -> Any:
    """
    Call Gemini API with automatic fallback from Pro to Flash on quota errors.

    Args:
        model_id: The model to use (e.g., "gemini-3-pro-preview")
        contents: The content to send to the model
        config: Optional GenerateContentConfig
        operation: Description of the operation for logging

    Returns:
        The API response

    Raises:
        Exception: If both Pro and Flash fail
    """
    if not _available:
        raise RuntimeError(_error or "Gemini client not initialized")

    try:
        if config:
            return client.models.generate_content(model=model_id, contents=contents, config=config)
        else:
            return client.models.generate_content(model=model_id, contents=contents)
    except Exception as e:
        error_msg = str(e).lower()
        # Check for quota/rate limit errors and if we're using a Pro model
        if ("quota" in error_msg or "rate" in error_msg or "resource" in error_msg) and "pro" in model_id.lower():
            log_progress(f"{operation}: Pro model quota exceeded, falling back to Flash...")
            flash_model = MODELS["flash"]
            try:
                if config:
                    response = client.models.generate_content(model=flash_model, contents=contents, config=config)
                else:
                    response = client.models.generate_content(model=flash_model, contents=contents)
                log_progress(f"{operation}: Completed with Flash fallback")
                return response
            except Exception as fallback_error:
                raise Exception(f"Both Pro and Flash failed. Pro error: {str(e)}. Flash error: {str(fallback_error)}")
        raise
