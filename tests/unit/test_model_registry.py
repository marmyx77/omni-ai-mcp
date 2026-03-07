"""
Unit tests for ModelRegistry (v4.0.0)

Tests category resolution, cache behaviour, static fallbacks,
and deprecation detection — all without real API calls.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.model_registry import ModelRegistry, CATEGORY_PRIORITIES, STATIC_FALLBACKS


def _make_registry(available_models: list) -> ModelRegistry:
    """Return a ModelRegistry pre-loaded with a fake available list."""
    reg = ModelRegistry()
    reg._available_model_names = available_models
    reg._cache_timestamp = time.time()
    return reg


class TestCategoryPriorities:
    def test_all_required_categories_present(self):
        required = {"text_pro", "text_flash", "text_flash_lite", "image", "video", "tts", "deep_research"}
        assert required.issubset(set(CATEGORY_PRIORITIES.keys()))

    def test_each_category_has_at_least_one_candidate(self):
        for cat, candidates in CATEGORY_PRIORITIES.items():
            assert len(candidates) >= 1, f"{cat} has no candidates"

    def test_static_fallbacks_cover_all_categories(self):
        for cat in CATEGORY_PRIORITIES:
            assert cat in STATIC_FALLBACKS, f"{cat} missing from STATIC_FALLBACKS"


class TestResolve:
    def test_returns_first_available_candidate(self):
        reg = _make_registry(["gemini-3.1-pro-preview", "gemini-2.5-flash"])
        assert reg.resolve("text_pro") == "gemini-3.1-pro-preview"

    def test_skips_unavailable_and_returns_second(self):
        reg = _make_registry(["gemini-2.5-pro"])  # 3.1-pro not available
        result = reg.resolve("text_pro")
        # Should fall through to first available candidate in priority list
        assert result == "gemini-2.5-pro"

    def test_uses_static_fallback_when_nothing_matches(self):
        reg = _make_registry(["some-unknown-model"])
        with pytest.warns(RuntimeWarning, match="No available model found"):
            result = reg.resolve("text_pro")
        assert result == STATIC_FALLBACKS["text_pro"]

    def test_empty_available_list_uses_first_candidate(self):
        """When discovery fails (empty list), use first priority candidate."""
        reg = _make_registry([])
        result = reg.resolve("text_flash")
        assert result == CATEGORY_PRIORITIES["text_flash"][0]

    def test_resolved_cache_hit(self):
        reg = _make_registry(["gemini-3.1-pro-preview"])
        first = reg.resolve("text_pro")
        # Corrupt the available list — should still return cached result
        reg._available_model_names = []
        second = reg.resolve("text_pro")
        assert first == second

    def test_unknown_category_uses_fallback(self):
        reg = _make_registry(["gemini-2.5-flash"])
        with pytest.warns(RuntimeWarning):
            result = reg.resolve("nonexistent_category")
        assert result == "gemini-2.5-flash"  # STATIC_FALLBACKS default


class TestListAvailable:
    def test_returns_dict_with_all_categories(self):
        reg = _make_registry(["gemini-3.1-pro-preview", "gemini-2.5-flash",
                               "gemini-2.5-flash-lite", "veo-3.1-generate-preview",
                               "gemini-2.5-flash-preview-tts"])
        result = reg.list_available()
        for cat in CATEGORY_PRIORITIES:
            assert cat in result

    def test_no_deprecated_when_all_available(self):
        # Put all config defaults into the available list
        from app.core.config import config
        reg = _make_registry([
            config.model_pro, config.model_flash,
            config.model_image_pro, config.model_veo31,
        ])
        result = reg.list_available()
        assert "deprecated_in_config" not in result


class TestCheckDeprecated:
    def test_detects_deprecated_pro_model(self):
        from app.core.config import config
        # Available list does NOT contain the current config pro model
        reg = _make_registry(["gemini-2.5-pro"])
        deprecated = reg.check_deprecated()
        assert any(config.model_pro in d for d in deprecated)

    def test_empty_when_all_current(self):
        from app.core.config import config
        reg = _make_registry([
            config.model_pro, config.model_flash,
            config.model_image_pro, config.model_veo31,
        ])
        assert reg.check_deprecated() == []

    def test_empty_when_discovery_failed(self):
        reg = _make_registry([])  # Discovery failed = empty list
        assert reg.check_deprecated() == []


class TestInvalidateCache:
    def test_invalidate_clears_resolved_and_names(self):
        reg = _make_registry(["gemini-3.1-pro-preview"])
        reg.resolve("text_pro")
        assert reg._resolved  # Cache populated
        reg.invalidate_cache()
        assert reg._available_model_names is None
        assert reg._resolved == {}


class TestCacheTTL:
    def test_stale_cache_triggers_refresh(self):
        reg = ModelRegistry()
        reg._available_model_names = ["gemini-2.5-flash"]
        reg._cache_timestamp = time.time() - 9999  # Expired

        refreshed = []

        def fake_refresh():
            refreshed.append(True)
            reg._available_model_names = ["gemini-3.1-pro-preview"]
            reg._cache_timestamp = time.time()

        reg._refresh_cache = fake_refresh
        reg.resolve("text_pro")
        assert refreshed, "Expected cache refresh on stale TTL"
