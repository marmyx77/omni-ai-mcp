"""
Dynamic Model Registry (v4.6.0, multi-scheme + probing since v4.8.0)

Discovers the models the Gemini API actually exposes and picks, per category,
the newest one that matches the category's naming pattern(s). No hardcoded
"latest" IDs anywhere: when Google ships gemini-4.1-flash, it is picked up on
the next cache refresh without a release of this package.

Resolution order for a category:
  1. explicit env override (GEMINI_MODEL_* set in the environment) — always wins
  2. auto-detect: newest API model matching one of the category patterns
  3. static fallback list: first candidate the API lists, else the first one a
     direct models.get() confirms ("probed": the API stopped listing some
     families, e.g. Veo in Oct 2026, while still serving them), else the first
     candidate if discovery failed altogether
  4. config default (the same value the env var would default to)

Naming schemes: a category may list several anchored patterns, oldest naming
scheme first. A match on a newer scheme always outranks an older one, because
version numbers are not comparable across schemes (Nano Banana 2.1 is newer
than gemini-3.1-flash-image although 2.1 < 3.1).
"""

import functools
import os
import re
import threading
import time
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core import config, log_progress


# Sort key for a model ID: (scheme, major, minor, stable_bonus). Higher wins.
_VersionKey = Tuple[int, int, int, int]

# Words that, right after the version, mark a non-flagship family. Used by the
# flagship ("pro") pattern so Gemini 4 codenames (gemini-4-argon) qualify while
# flash/lite/live/... never do. Codenames only count from Gemini 4 on: older
# single-word IDs (gemini-2.0-exp) were experiments, not flagships.
_NON_FLAGSHIP = "flash|lite|live|tts|image|transcribe|embedding|robotics|omni|nano|computer|exp|latest|thinking"
_FLAGSHIP_PATTERN = (
    r"^gemini-"
    r"(?=\d+(?:\.\d+)?-pro(?:-preview)?$"                              # any -pro release
    rf"|(?:[4-9]|[1-9]\d+)(?:\.\d+)?-(?!(?:{_NON_FLAGSHIP})$)[a-z]+(?:-preview)?$)"  # 4+ codename
    r"(\d+)(?:\.(\d+))?-[a-z]+(?:-preview)?$"
)


@dataclass(frozen=True)
class CategorySpec:
    """How to recognise and rank the models of one category."""

    patterns: Tuple[str, ...]          # anchored regexes, oldest naming scheme first
    fallbacks: List[str]               # priority-ordered static candidates
    env_var: str                       # explicit override (always wins)
    config_attr: str                   # Config attribute holding the default
    version_groups: Tuple[int, int] = (1, 2)  # regex groups for (major, minor)
    _compiled: Tuple[re.Pattern, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_compiled", tuple(re.compile(p) for p in self.patterns))

    @property
    def pattern(self) -> str:
        """Newest naming scheme (kept for callers that expect a single pattern)."""
        return self.patterns[-1]

    def version_key(self, model_id: str) -> Optional[_VersionKey]:
        """Return the ranking key if model_id belongs to this category, else None."""
        for scheme, compiled in reversed(list(enumerate(self._compiled))):
            match = compiled.match(model_id)
            if not match:
                continue
            major_group, minor_group = self.version_groups
            major = int(match.group(major_group) or 0)
            minor = int(match.group(minor_group) or 0)
            stable_bonus = 0 if "preview" in model_id else 1
            return (scheme, major, minor, stable_bonus)
        return None


def _spec(patterns, fallbacks, env_var, config_attr, version_groups=(1, 2)) -> CategorySpec:
    if isinstance(patterns, str):
        patterns = (patterns,)
    return CategorySpec(tuple(patterns), list(fallbacks), env_var, config_attr, version_groups)


# Anchored patterns deliberately exclude variants that are NOT drop-in
# replacements: -live, -transcribe, -customtools, -computer-use, -native-audio,
# -image, -tts, -translate, -robotics, -embedding.
CATEGORY_SPECS: Dict[str, CategorySpec] = {
    "text_pro": _spec(
        # gemini-3.1-pro-preview, gemini-2.5-pro, and Gemini 4 codenames (gemini-4-argon)
        _FLAGSHIP_PATTERN,
        ["gemini-4-argon", "gemini-3.1-pro-preview", "gemini-2.5-pro"],
        "GEMINI_MODEL_PRO", "model_pro",
    ),
    "text_flash": _spec(
        r"^gemini-(\d+)(?:\.(\d+))?-flash(?:-preview)?$",
        ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash"],
        "GEMINI_MODEL_FLASH", "model_flash",
    ),
    "text_flash_lite": _spec(
        r"^gemini-(\d+)(?:\.(\d+))?-flash-lite(?:-preview)?$",
        ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
        "GEMINI_MODEL_FLASH_LITE", "model_flash_lite",
    ),
    "image": _spec(
        (r"^gemini-(\d+)(?:\.(\d+))?-pro-image(?:-preview)?$",
         r"^gemini-nano-banana-pro-(\d+)(?:\.(\d+))?(?:-preview)?$"),
        ["gemini-3-pro-image", "gemini-3-pro-image-preview"],
        "GEMINI_MODEL_IMAGE_PRO", "model_image_pro",
    ),
    "image_flash": _spec(
        (r"^gemini-(\d+)(?:\.(\d+))?-flash-image(?:-preview)?$",
         r"^gemini-nano-banana-(\d+)(?:\.(\d+))?(?:-preview)?$"),
        ["gemini-nano-banana-2.1", "gemini-3.1-flash-image"],
        "GEMINI_MODEL_IMAGE_FLASH", "model_image_flash",
    ),
    "image_lite": _spec(
        (r"^gemini-(\d+)(?:\.(\d+))?-flash-lite-image(?:-preview)?$",
         r"^gemini-nano-banana-lite-(\d+)(?:\.(\d+))?(?:-preview)?$"),
        ["gemini-3.1-flash-lite-image"],
        "GEMINI_MODEL_IMAGE_LITE", "model_image_lite",
    ),
    "video": _spec(
        # Gemini Omni Flash (Veo 3.1 Preview shut down 2026-10-22 in the Gemini API)
        r"^gemini-omni-(\d+)(?:\.(\d+))?-flash(?:-preview)?$",
        ["gemini-omni-1.1-flash"],
        "GEMINI_MODEL_VIDEO", "model_video",
    ),
    "tts": _spec(
        r"^gemini-(\d+)(?:\.(\d+))?-flash(?:-preview)?-tts(?:-preview)?$",
        ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"],
        "GEMINI_MODEL_TTS_FLASH", "model_tts_flash",
    ),
    "tts_lite": _spec(
        r"^gemini-(\d+)(?:\.(\d+))?-flash-lite(?:-preview)?-tts(?:-preview)?$",
        ["gemini-3.8-flash-lite-tts"],
        "GEMINI_MODEL_TTS_LITE", "model_tts_lite",
    ),
    "transcribe": _spec(
        # dedicated speech-to-text models; the -live variant (WebSocket) is excluded by the anchor
        r"^gemini-(\d+)(?:\.(\d+))?-transcribe(?:-preview)?$",
        ["gemini-3.5-transcribe"],
        "GEMINI_MODEL_TRANSCRIBE", "model_transcribe",
    ),
    "music": _spec(
        # full songs: lyria-3.5, lyria-3-pro-preview (clip and realtime are excluded)
        r"^lyria-(\d+)(?:\.(\d+))?(?:-pro)?(?:-preview)?$",
        ["lyria-3.5", "lyria-3-pro-preview"],
        "GEMINI_MODEL_MUSIC", "model_music",
    ),
    "music_clip": _spec(
        r"^lyria-(\d+)(?:\.(\d+))?-clip(?:-preview)?$",
        ["lyria-3-clip-preview"],
        "GEMINI_MODEL_MUSIC_CLIP", "model_music_clip",
    ),
    "deep_research": _spec(
        # deep-research-preview-MM-YYYY → rank by (year, month)
        r"^deep-research-preview-(\d{2})-(\d{4})$",
        ["deep-research-preview-04-2026"],
        "GEMINI_MODEL_DEEP_RESEARCH", "model_deep_research",
        version_groups=(2, 1),
    ),
    "deep_research_max": _spec(
        r"^deep-research-max-preview-(\d{2})-(\d{4})$",
        ["deep-research-max-preview-04-2026"],
        "GEMINI_MODEL_DEEP_RESEARCH_MAX", "model_deep_research_max",
        version_groups=(2, 1),
    ),
    "agent": _spec(
        # Antigravity managed agent: antigravity-preview-MM-YYYY (the -latest alias is not ranked)
        r"^antigravity-preview-(\d{2})-(\d{4})$",
        ["antigravity-preview-09-2026"],
        "GEMINI_MODEL_AGENT", "model_agent",
        version_groups=(2, 1),
    ),
    "embedding": _spec(
        # gemini-embedding-2 (multimodal) > gemini-embedding-001 (text only)
        r"^gemini-embedding-(\d+)(?:-preview)?$",
        ["gemini-embedding-2", "gemini-embedding-001"],
        "GEMINI_MODEL_EMBEDDING", "model_embedding",
        version_groups=(1, 1),
    ),
    "robotics": _spec(
        # embodied/spatial reasoning; the -streaming (Live API) variant is excluded
        r"^gemini-robotics-er-(\d+)(?:\.(\d+))?(?:-preview)?$",
        ["gemini-robotics-er-2-preview"],
        "GEMINI_MODEL_ROBOTICS", "model_robotics",
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
_LAST_RESORT_MODEL = "gemini-3.8-flash"


@dataclass(frozen=True)
class Resolution:
    """Where a resolved model came from — surfaced by gemini_list_models."""

    model: str
    source: str                 # "env" | "auto" | "fallback" | "probed" | "config"
    candidates: List[str]       # ranked auto-detect matches (best first)


def _locked(method):
    """Run a ModelRegistry method under the instance's re-entrant lock."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class ModelRegistry:
    """
    Discovers available Gemini models via API and resolves the best one per category.

    Falls back to static candidates (verified by name when unlisted), then config
    values, if discovery fails. Cache is refreshed every hour.
    """

    def __init__(self) -> None:
        self._available_model_names: Optional[List[str]] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = _CACHE_TTL
        self._resolved: Dict[str, Resolution] = {}
        self._probed: Dict[str, bool] = {}
        # FastMCP runs sync tools in worker threads: refresh/resolve must not interleave
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ cache

    def _is_cache_valid(self) -> bool:
        return (
            self._available_model_names is not None
            and (time.time() - self._cache_timestamp) < self._cache_ttl
        )

    def _refresh_cache(self) -> None:
        """Fetch available models from the API and populate cache."""
        self._resolved = {}
        self._probed = {}
        try:
            from .gemini import client, _available

            if not _available or client is None:
                self._available_model_names = []
                self._cache_timestamp = time.time()
                self._cache_ttl = _FAILURE_RETRY_TTL
                return

            models = client.models.list(config={"page_size": 1000})
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

    @_locked
    def _ensure_fresh(self) -> None:
        if not self._is_cache_valid():
            self._refresh_cache()

    @_locked
    def _probe(self, model_id: str) -> bool:
        """True if the API serves model_id even though models.list() omits it."""
        if model_id in self._probed:
            return self._probed[model_id]
        ok = False
        try:
            from .gemini import client, _available
            if _available and client is not None:
                client.models.get(model=model_id)
                ok = True
        except Exception:
            ok = False
        self._probed[model_id] = ok
        return ok

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

    @_locked
    def rank_candidates(self, category: str) -> List[str]:
        """Available models matching the category patterns, newest first."""
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

    @_locked
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
            warnings.warn(
                f"model_registry: Unknown category '{category}', "
                f"using last-resort '{_LAST_RESORT_MODEL}'",
                RuntimeWarning,
                stacklevel=3,
            )
            return Resolution(_LAST_RESORT_MODEL, "config", [])

        override = os.environ.get(spec.env_var, "").strip()
        candidates = self.rank_candidates(category)
        if override:
            return Resolution(override, "env", candidates)

        if self.autodetect_enabled() and candidates:
            return Resolution(candidates[0], "auto", candidates)

        available = set(self._available_model_names or [])
        if not available:
            # Discovery failed: trust the first static candidate.
            return Resolution(spec.fallbacks[0], "fallback", candidates)
        for candidate in spec.fallbacks:
            if candidate in available:
                return Resolution(candidate, "fallback", candidates)
        for candidate in spec.fallbacks:
            if self._probe(candidate):
                return Resolution(candidate, "probed", candidates)

        fallback = getattr(config, spec.config_attr, None) or _LAST_RESORT_MODEL
        warnings.warn(
            f"model_registry: No available model found for category '{category}', "
            f"using static fallback '{fallback}'",
            RuntimeWarning,
            stacklevel=3,
        )
        return Resolution(fallback, "config", candidates)

    # ------------------------------------------------------------ reporting

    @_locked
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

    @_locked
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

    @_locked
    def invalidate_cache(self) -> None:
        """Force cache refresh on next access."""
        self._available_model_names = None
        self._cache_timestamp = 0.0
        self._resolved = {}
        self._probed = {}


# Global registry instance
model_registry = ModelRegistry()
