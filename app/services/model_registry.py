"""
Dynamic Model Registry

Discovers and validates available Gemini models at runtime via the API.
Selects the best available model per category with static config fallback.
"""

import time
import warnings
from typing import Dict, List, Optional

from ..core import config, log_progress


# Priority-ordered candidates per category
CATEGORY_PRIORITIES: Dict[str, List[str]] = {
    "text_pro": [
        "gemini-3.1-pro-preview",
        "gemini-3-pro-preview",
        "gemini-2.5-pro",
        "gemini-2.5-pro-preview",
    ],
    "text_flash": [
        "gemini-3.1-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ],
    "text_flash_lite": [
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
    ],
    "image": [
        "gemini-3.1-pro-image-preview",
        "gemini-3-pro-image-preview",
        "imagen-3.0-generate-002",
    ],
    "video": [
        "veo-3.1-generate-preview",
        "veo-3.0-generate-001",
        "veo-2.0-generate-001",
    ],
    "tts": [
        "gemini-2.5-flash-preview-tts",
        "gemini-2.5-pro-preview-tts",
    ],
    "deep_research": [
        "deep-research-pro-preview",
    ],
}

# Static fallback values (from config, which reads env vars)
STATIC_FALLBACKS: Dict[str, str] = {
    "text_pro": config.model_pro,
    "text_flash": config.model_flash,
    "text_flash_lite": config.model_flash,
    "image": config.model_image_pro,
    "video": config.model_veo31,
    "tts": config.model_tts_flash,
    "deep_research": config.model_deep_research,
}

_CACHE_TTL = 3600  # 1 hour


class ModelRegistry:
    """
    Discovers available Gemini models via API and resolves the best one per category.

    Falls back to static config values if discovery fails or model is unavailable.
    Cache is refreshed every hour to pick up newly available models.
    """

    def __init__(self) -> None:
        self._available_model_names: Optional[List[str]] = None
        self._cache_timestamp: float = 0.0
        self._resolved: Dict[str, str] = {}

    def _is_cache_valid(self) -> bool:
        return (
            self._available_model_names is not None
            and (time.time() - self._cache_timestamp) < _CACHE_TTL
        )

    def _refresh_cache(self) -> None:
        """Fetch available models from the API and populate cache."""
        try:
            from .gemini import client, _available

            if not _available or client is None:
                return

            models = client.models.list()
            self._available_model_names = [
                m.name.replace("models/", "") for m in models
            ]
            self._cache_timestamp = time.time()
            self._resolved.clear()  # Invalidate resolved cache on refresh
            log_progress(
                f"model_registry: Discovered {len(self._available_model_names)} models"
            )
        except Exception as e:
            log_progress(f"model_registry: Discovery failed ({e}), using config defaults")
            self._available_model_names = []

    def _ensure_fresh(self) -> None:
        if not self._is_cache_valid():
            self._refresh_cache()

    def resolve(self, category: str) -> str:
        """
        Return the best available model for a category.

        Priority: (1) previously resolved cache, (2) first matching available model,
        (3) static config fallback.
        """
        if category in self._resolved and self._is_cache_valid():
            return self._resolved[category]

        self._ensure_fresh()

        candidates = CATEGORY_PRIORITIES.get(category, [])
        available = set(self._available_model_names or [])

        for candidate in candidates:
            if not available or candidate in available:
                # If available list is empty (discovery failed), use first candidate
                self._resolved[category] = candidate
                return candidate

        # Fall back to static config value
        fallback = STATIC_FALLBACKS.get(category, "gemini-2.5-flash")
        warnings.warn(
            f"model_registry: No available model found for category '{category}', "
            f"using static fallback '{fallback}'",
            RuntimeWarning,
            stacklevel=2,
        )
        self._resolved[category] = fallback
        return fallback

    def list_available(self) -> Dict[str, object]:
        """Return all available models per category and deprecation warnings."""
        self._ensure_fresh()

        result: Dict[str, object] = {}
        for category in CATEGORY_PRIORITIES:
            result[category] = self.resolve(category)

        deprecated = self.check_deprecated()
        if deprecated:
            result["deprecated_in_config"] = deprecated

        return result

    def check_deprecated(self) -> List[str]:
        """Return config model values that are no longer in the available list."""
        self._ensure_fresh()

        if not self._available_model_names:
            return []  # Discovery failed — can't report deprecations

        available = set(self._available_model_names)
        deprecated = []

        for attr in ("model_pro", "model_flash", "model_image_pro", "model_veo31"):
            value = getattr(config, attr, None)
            if value and value not in available:
                deprecated.append(f"{attr}={value}")

        return deprecated

    def invalidate_cache(self) -> None:
        """Force cache refresh on next access."""
        self._available_model_names = None
        self._resolved.clear()


# Global registry instance
model_registry = ModelRegistry()
