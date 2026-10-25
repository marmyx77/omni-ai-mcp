"""
Gemini AI Service

This module provides the core Gemini client and model configurations.
It handles client initialization, model mappings, and API calls with fallback.
"""

import os
import re
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
        client = genai.Client(
            api_key=API_KEY,
            http_options=genai_types.HttpOptions(timeout=config.request_timeout * 1000),  # ms
        )
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


_QUOTA_PATTERN = re.compile(
    r"\b(?:resource[_ ]exhausted|quota|rate[ -]?limit(?:ed|s)?|too many requests)\b", re.IGNORECASE
)


def is_quota_error(exc: BaseException) -> bool:
    """True for a per-model quota / rate-limit error (HTTP 429), the only case a Flash retry helps.

    A project spending cap is also a 429 but blocks every model, so it is excluded.
    """
    message = str(exc)
    if "spending cap" in message.lower():
        return False
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 429:
        return True
    return bool(_QUOTA_PATTERN.search(message))


def _generate(model_id: str, contents: Any, config: Any) -> Any:
    if config:
        return client.models.generate_content(model=model_id, contents=contents, config=config)
    return client.models.generate_content(model=model_id, contents=contents)


def generate_with_fallback(
    model_id: str,
    contents: Any,
    config: Any = None,
    operation: str = "request",
    allow_fallback: bool = True,
) -> Any:
    """
    Call Gemini API, retrying once on Flash when the model hits a quota / rate limit.

    Args:
        model_id: The model to use (e.g., "gemini-4-argon")
        contents: The content to send to the model
        config: Optional GenerateContentConfig
        operation: Description of the operation for logging
        allow_fallback: False when the caller asked for this exact model: then a
            quota error is raised instead of silently answering with another model

    Returns:
        The API response

    Raises:
        Exception: the original error, or both errors if the Flash retry also fails
    """
    if not _available:
        raise RuntimeError(_error or "Gemini client not initialized")

    try:
        return _generate(model_id, contents, config)
    except Exception as e:
        flash_model = MODELS["flash"]
        if not (allow_fallback and is_quota_error(e) and model_id != flash_model):
            raise
        log_progress(f"{operation}: {model_id} quota exceeded, falling back to {flash_model}...")
        try:
            response = _generate(flash_model, contents, config)
        except Exception as fallback_error:
            raise Exception(
                f"Both {model_id} and {flash_model} failed. First error: {e}. Fallback error: {fallback_error}"
            ) from fallback_error
        log_progress(f"{operation}: Completed with Flash fallback")
        return response
