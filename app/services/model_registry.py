"""
Dynamic Model Registry (v4.6.0)

Discovers the models the Gemini API actually exposes and picks, per category,
the newest one that matches the category's naming pattern. No hardcoded
"latest" IDs anywhere: when Google ships gemini-4.0-flash, it is picked up on
the next cache refresh without a release of this package.

Resolution order for a category:
  1. explicit env override (GEMINI_MODEL_* set in the environment) — always wins
  2. auto-detect: newest API model matching the category pattern
  3. static fallback list (first candidate the API exposes, or the first one if
     discovery failed)
  4. config default (the same value the env var would default to)
"""

import os
import re
import time
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core import config, log_progress


# Sort key for a model ID: (major, minor, stable_bonus). Higher wins.
_VersionKey = Tuple[int, int, int]


@dataclass(frozen=True)
class CategorySpec:
    """How to recognise and rank the models of one category."""

    pattern: str                      # anchored regex; groups 1-2 = major/minor
    fallbacks: List[str]              # priority-ordered static candidates
    env_var: str                      # explicit override (always wins)
    config_attr: str                  # Config attribute holding the default
    version_groups: Tuple[int, int] = (1, 2)  # regex groups for (major, minor)
    _compiled: re.Pattern = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_compiled", re.compile(self.pattern))

    def version_key(self, model_id: str) -> Optional[_VersionKey]:
        """Return the ranking key if model_id belongs to this category, else None."""
        match = self._compiled.match(model_id)
        if not match:
            return None
        major_group, minor_group = self.version_groups
        major = int(match.group(major_group) or 0)
        minor = int(match.group(minor_group) or 0)
        stable_bonus = 0 if "preview" in model_id else 1
        return (major, minor, stable_bonus)


# Anchored patterns deliberately exclude variants that are NOT drop-in
# replacements: -live, -transcribe, -customtools, -computer-use, -native-audio,
# -image, -tts, -translate, -robotics, -embedding.
CATEGORY_SPECS: Dict[str, CategorySpec] = {
    "text_pro": CategorySpec(
        pattern=r"^gemini-(\d+)(?:\.(\d+))?-pro(?:-preview)?$",
        fallbacks=["gemini-3.1-pro-preview", "gemini-2.5-pro"],
        env_var="GEMINI_MODEL_PRO",
        config_attr="model_pro",
    ),
    "text_flash": CategorySpec(
        pattern=r"^gemini-(\d+)(?:\.(\d+))?-flash(?:-preview)?$",
        fallbacks=["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"],
        env_var="GEMINI_MODEL_FLASH",
        config_attr="model_flash",
    ),
    "text_flash_lite": CategorySpec(
        pattern=r"^gemini-(\d+)(?:\.(\d+))?-flash-lite(?:-preview)?$",
        fallbacks=["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
        env_var="GEMINI_MODEL_FLASH_LITE",
        config_attr="model_flash_lite",
    ),
    "image": CategorySpec(
        pattern=r"^gemini-(\d+)(?:\.(\d+))?-pro-image(?:-preview)?$",
        fallbacks=["gemini-3-pro-image", "gemini-3-pro-image-preview"],
        env_var="GEMINI_MODEL_IMAGE_PRO",
        config_attr="model_image_pro",
    ),
    "image_flash": CategorySpec(
        pattern=r"^gemini-(\d+)(?:\.(\d+))?-flash-image(?:-preview)?$",
        fallbacks=["gemini-3.1-flash-image", "gemini-2.5-flash-image"],
        env_var="GEMINI_MODEL_IMAGE_FLASH",
        config_attr="model_image_flash",
    ),
    "video": CategorySpec(
        pattern=r"^veo-(\d+)(?:\.(\d+))?-generate(?:-preview|-\d{3})?$",
        fallbacks=["veo-3.1-generate-preview"],
        env_var="GEMINI_MODEL_VEO31",
        config_attr="model_veo31",
    ),
    "video_fast": CategorySpec(
        pattern=r"^veo-(\d+)(?:\.(\d+))?-fast-generate(?:-preview|-\d{3})?$",
        fallbacks=["veo-3.1-fast-generate-preview"],
        env_var="GEMINI_MODEL_VEO31_FAST",
        config_attr="model_veo31_fast",
    ),
    "video_lite": CategorySpec(
        pattern=r"^veo-(\d+)(?:\.(\d+))?-lite-generate(?:-preview|-\d{3})?$",
        fallbacks=["veo-3.1-lite-generate-preview"],
        env_var="GEMINI_MODEL_VEO31_LITE",
        config_attr="model_veo31_lite",
    ),
    "tts": CategorySpec(
        pattern=r"^gemini-(\d+)(?:\.(\d+))?-flash(?:-preview)?-tts(?:-preview)?$",
        fallbacks=["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"],
        env_var="GEMINI_MODEL_TTS_FLASH",
        config_attr="model_tts_flash",
    ),
    "tts_pro": CategorySpec(
        pattern=r"^gemini-(\d+)(?:\.(\d+))?-pro(?:-preview)?-tts(?:-preview)?$",
        fallbacks=["gemini-2.5-pro-preview-tts"],
        env_var="GEMINI_MODEL_TTS_PRO",
        config_attr="model_tts_pro",
    ),
    "deep_research": CategorySpec(
        # deep-research-preview-MM-YYYY → rank by (year, month)
        pattern=r"^deep-research-preview-(\d{2})-(\d{4})$",
        fallbacks=["deep-research-preview-04-2026"],
        env_var="GEMINI_MODEL_DEEP_RESEARCH",
        config_attr="model_deep_research",
        version_groups=(2, 1),
    ),
}

# Kept for callers that only need the static candidates (tests, docs).
CATEGORY_PRIORITIES: Dict[str, List[str]] = {
    name: list(spec.fallbacks) for name, spec in CATEGORY_SPECS.items()
}

STATIC_FALLBACKS: Dict[str, str] = {
    name: getattr(config, spec.config_attr) for name, spec in CATEGORY_SPECS.items()
}

_CACHE_TTL = 3600          # 1 hour: how long a successful discovery is trusted
_FAILURE_RETRY_TTL = 300   # 5 minutes: back-off after a failed discovery
_LAST_RESORT_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class Resolution:
    """Where a resolved model came from — surfaced by gemini_list_models."""

    model: str
    source: str                 # "env" | "auto" | "fallback" | "config"
    candidates: List[str]       # ranked auto-detect matches (best first)


class ModelRegistry:
    """
    Discovers available Gemini models via API and resolves the best one per category.

    Falls back to static candidates, then config values, if discovery fails.
    Cache is refreshed every hour to pick up newly available models.
    """

    def __init__(self) -> None:
        self._available_model_names: Optional[List[str]] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = _CACHE_TTL
        self._resolved: Dict[str, Resolution] = {}

    # ------------------------------------------------------------------ cache

    def _is_cache_valid(self) -> bool:
        return (
            self._available_model_names is not None
            and (time.time() - self._cache_timestamp) < self._cache_ttl
        )

    def _refresh_cache(self) -> None:
        """Fetch available models from the API and populate cache."""
        self._resolved = {}
        try:
            from .gemini import client, _available

            if not _available or client is None:
                self._available_model_names = []
                self._cache_timestamp = time.time()
                self._cache_ttl = _FAILURE_RETRY_TTL
                return

            models = client.models.list()
            self._available_model_names = [
                m.name.replace("models/", "") for m in models
            ]
            self._cache_timestamp = time.time()
            self._cache_ttl = _CACHE_TTL
            log_progress(
                f"model_registry: Discovered {len(self._available_model_names)} models"
            )
        except Exception as e:
            log_progress(f"model_registry: Discovery failed ({e}), using fallbacks")
            self._available_model_names = []
            self._cache_timestamp = time.time()
            self._cache_ttl = _FAILURE_RETRY_TTL

    def _ensure_fresh(self) -> None:
        if not self._is_cache_valid():
            self._refresh_cache()

    @property
    def discovery_succeeded(self) -> bool:
        """True when the (fresh) discovery got a non-empty list from the API."""
        self._ensure_fresh()
        return bool(self._available_model_names)

    @property
    def available_models(self) -> List[str]:
        self._ensure_fresh()
        return list(self._available_model_names or [])

    # -------------------------------------------------------------- resolve

    @staticmethod
    def autodetect_enabled() -> bool:
        return config.model_autodetect

    def rank_candidates(self, category: str) -> List[str]:
        """Available models matching the category pattern, newest first."""
        spec = CATEGORY_SPECS.get(category)
        if spec is None:
            return []
        keyed = []
        for name in self._available_model_names or []:
            key = spec.version_key(name)
            if key is not None:
                keyed.append((key, name))
        keyed.sort(key=lambda kv: (kv[0], kv[1]), reverse=True)
        return [name for _, name in keyed]

    def explain(self, category: str) -> Resolution:
        """Resolve a category and say where the answer came from."""
        if category in self._resolved and self._is_cache_valid():
            return self._resolved[category]

        self._ensure_fresh()
        resolution = self._compute(category)
        self._resolved[category] = resolution
        return resolution

    def resolve(self, category: str) -> str:
        """Return the best available model ID for a category."""
        return self.explain(category).model

    def _compute(self, category: str) -> Resolution:
        spec = CATEGORY_SPECS.get(category)
        if spec is None:
            fallback = _LAST_RESORT_MODEL
            warnings.warn(
                f"model_registry: Unknown category '{category}', "
                f"using last-resort '{fallback}'",
                RuntimeWarning,
                stacklevel=3,
            )
            return Resolution(fallback, "config", [])

        override = os.environ.get(spec.env_var, "").strip()
        candidates = self.rank_candidates(category)
        if override:
            return Resolution(override, "env", candidates)

        if self.autodetect_enabled() and candidates:
            return Resolution(candidates[0], "auto", candidates)

        available = set(self._available_model_names or [])
        for candidate in spec.fallbacks:
            if not available or candidate in available:
                return Resolution(candidate, "fallback", candidates)

        fallback = getattr(config, spec.config_attr, None) or _LAST_RESORT_MODEL
        warnings.warn(
            f"model_registry: No available model found for category '{category}', "
            f"using static fallback '{fallback}'",
            RuntimeWarning,
            stacklevel=3,
        )
        return Resolution(fallback, "config", candidates)

    # ------------------------------------------------------------ reporting

    def list_available(self) -> Dict[str, object]:
        """Return the resolved model per category plus deprecation warnings."""
        self._ensure_fresh()

        result: Dict[str, object] = {}
        for category in CATEGORY_SPECS:
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

        for spec in CATEGORY_SPECS.values():
            value = getattr(config, spec.config_attr, None)
            if value and value not in available:
                deprecated.append(f"{spec.config_attr}={value}")

        return deprecated

    def invalidate_cache(self) -> None:
        """Force cache refresh on next access."""
        self._available_model_names = None
        self._cache_timestamp = 0.0
        self._resolved = {}


# Global registry instance
model_registry = ModelRegistry()
