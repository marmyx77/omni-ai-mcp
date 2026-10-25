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
    "pro": "text_pro",            # Flagship reasoning (Gemini 4 Argon since v4.8.0)
    "flash": "text_flash",        # Balanced speed/quality for standard tasks
    "fast": "text_flash",         # High-volume, simple tasks (same as flash)
    "flash-lite": "text_flash_lite",
    "robotics": "robotics",       # Embodied/spatial reasoning (points, boxes, trajectories)
})

IMAGE_MODELS = _LazyModelMap({
    "pro": "image",               # Nano Banana Pro: highest quality, 4K, thinking
    "flash": "image_flash",       # Nano Banana 2.1: fast, panoramic formats, 14 references
    "lite": "image_lite",         # Nano Banana 2 Lite: lowest latency and cost
})

VIDEO_MODELS = _LazyModelMap({
    "omni": "video",              # Gemini Omni Flash: generate, edit, extend, interpolate
})

TTS_MODELS = _LazyModelMap({
    "flash": "tts",               # Gemini 3.8 Flash TTS: studio-grade, acting, dialects
    "lite": "tts_lite",           # Gemini 3.8 Flash-Lite TTS: fast, cost-efficient
    "pro": "tts",                 # kept for compatibility: the Flash TTS is now the flagship
})

MUSIC_MODELS = _LazyModelMap({
    "full": "music",              # Lyria 3.5: full-length songs (a couple of minutes)
    "clip": "music_clip",         # Lyria 3 Clip: 30-second clips and loops
})


def legacy_sampling(model_id: str, temperature: Optional[float]) -> Dict[str, Any]:
    """
    Sampling kwargs for GenerateContentConfig.

    temperature/top_p/top_k are deprecated and ignored from Gemini 3.6 on, and
    Google announces HTTP 400 for future generations: send temperature only to
    the 2.x and Gemma models that still honour it.
    """
    if temperature is None:
        return {}
    lower = (model_id or "").lower()
    if lower.startswith(("gemini-2.", "gemma-", "models/gemini-2.")):
        return {"temperature": temperature}
    return {}


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
        flash_model = MODELS["flash"]
        spending_cap = "spending cap" in error_msg
        if ("quota" in error_msg or "rate" in error_msg or "resource" in error_msg) \
                and model_id != flash_model and not spending_cap:
            log_progress(f"{operation}: {model_id} quota exceeded, falling back to {flash_model}...")
            try:
                if config:
                    response = client.models.generate_content(model=flash_model, contents=contents, config=config)
                else:
                    response = client.models.generate_content(model=flash_model, contents=contents)
                log_progress(f"{operation}: Completed with Flash fallback")
                return response
            except Exception as fallback_error:
                raise Exception(f"Both {model_id} and {flash_model} failed. First error: {str(e)}. Fallback error: {str(fallback_error)}")
        raise
