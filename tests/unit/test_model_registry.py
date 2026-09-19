"""
Unit tests for ModelRegistry (v4.6.0 auto-detect)

Tests version-aware auto-detection, env overrides, cache behaviour, static
fallbacks and deprecation detection — all without real API calls.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import config as app_config
from app.services.model_registry import (
    ModelRegistry,
    CATEGORY_SPECS,
    CATEGORY_PRIORITIES,
    STATIC_FALLBACKS,
    _FAILURE_RETRY_TTL,
)

# A realistic slice of what the API returned on 2026-09-19.
LIVE_SNAPSHOT = [
    "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro",
    "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts",
    "gemini-3-flash-preview", "gemini-3-pro-image", "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image", "gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview",
    "gemini-3.1-flash-live-preview", "gemini-3.1-flash-tts-preview",
    "gemini-3.1-pro-preview", "gemini-3.1-pro-preview-customtools",
    "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.5-transcribe",
    "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.8-live",
    "gemini-flash-latest", "gemini-pro-latest", "gemini-embedding-2",
    "veo-3.1-fast-generate-preview", "veo-3.1-generate-preview",
    "veo-3.1-lite-generate-preview",
    "deep-research-preview-04-2026", "deep-research-max-preview-04-2026",
    "deep-research-pro-preview-12-2025",
]


def _make_registry(available_models: list) -> ModelRegistry:
    """Return a ModelRegistry pre-loaded with a fake available list."""
    reg = ModelRegistry()
    reg._available_model_names = list(available_models)
    reg._cache_timestamp = time.time()
    return reg


@pytest.fixture(autouse=True)
def _no_env_overrides(monkeypatch):
    """Tests must not be affected by GEMINI_MODEL_* set in the developer's shell."""
    for spec in CATEGORY_SPECS.values():
        monkeypatch.delenv(spec.env_var, raising=False)
    monkeypatch.setattr(app_config, "model_autodetect", True)


class TestCategorySpecs:
    def test_all_required_categories_present(self):
        required = {"text_pro", "text_flash", "text_flash_lite", "image", "image_flash",
                    "video", "video_fast", "video_lite", "tts", "tts_pro", "deep_research"}
        assert required.issubset(set(CATEGORY_SPECS.keys()))

    def test_each_category_has_at_least_one_fallback(self):
        for cat, spec in CATEGORY_SPECS.items():
            assert len(spec.fallbacks) >= 1, f"{cat} has no fallbacks"

    def test_priorities_and_static_fallbacks_cover_all_categories(self):
        assert set(CATEGORY_PRIORITIES) == set(CATEGORY_SPECS)
        assert set(STATIC_FALLBACKS) == set(CATEGORY_SPECS)

    def test_every_fallback_matches_its_own_pattern(self):
        """A fallback that the pattern would reject is a typo waiting to bite."""
        for cat, spec in CATEGORY_SPECS.items():
            for candidate in spec.fallbacks:
                assert spec.version_key(candidate) is not None, f"{cat}: {candidate}"


class TestVersionKey:
    def test_parses_major_minor(self):
        spec = CATEGORY_SPECS["text_flash"]
        assert spec.version_key("gemini-3.8-flash") == (3, 8, 1)
        assert spec.version_key("gemini-3-flash-preview") == (3, 0, 0)

    def test_stable_outranks_preview_at_same_version(self):
        spec = CATEGORY_SPECS["image"]
        assert spec.version_key("gemini-3-pro-image") > spec.version_key("gemini-3-pro-image-preview")

    def test_newer_preview_outranks_older_stable(self):
        spec = CATEGORY_SPECS["text_pro"]
        assert spec.version_key("gemini-3.1-pro-preview") > spec.version_key("gemini-2.5-pro")

    @pytest.mark.parametrize("model_id", [
        "gemini-3.8-live", "gemini-3.1-flash-live-preview", "gemini-3.5-transcribe",
        "gemini-3.1-pro-preview-customtools", "gemini-3.1-flash-tts-preview",
        "gemini-3.1-flash-image", "gemini-flash-latest", "gemini-embedding-2",
    ])
    def test_flash_pattern_rejects_non_drop_in_variants(self, model_id):
        assert CATEGORY_SPECS["text_flash"].version_key(model_id) is None

    def test_flash_lite_not_matched_by_flash(self):
        assert CATEGORY_SPECS["text_flash"].version_key("gemini-3.5-flash-lite") is None
        assert CATEGORY_SPECS["text_flash_lite"].version_key("gemini-3.5-flash-lite") == (3, 5, 1)

    def test_deep_research_ranks_by_year_then_month(self):
        spec = CATEGORY_SPECS["deep_research"]
        assert spec.version_key("deep-research-preview-04-2026") == (2026, 4, 0)
        assert spec.version_key("deep-research-max-preview-04-2026") is None
        assert spec.version_key("deep-research-pro-preview-12-2025") is None


class TestAutoDetect:
    def test_picks_newest_flash_from_live_snapshot(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        assert reg.resolve("text_flash") == "gemini-3.8-flash"

    def test_picks_newest_flash_lite(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        assert reg.resolve("text_flash_lite") == "gemini-3.5-flash-lite"

    def test_pro_stays_on_newest_available_even_if_preview(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        assert reg.resolve("text_pro") == "gemini-3.1-pro-preview"

    def test_stable_image_beats_its_preview_twin(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        assert reg.resolve("image") == "gemini-3-pro-image"

    def test_video_variants(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        assert reg.resolve("video") == "veo-3.1-generate-preview"
        assert reg.resolve("video_fast") == "veo-3.1-fast-generate-preview"
        assert reg.resolve("video_lite") == "veo-3.1-lite-generate-preview"

    def test_tts_variants(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        assert reg.resolve("tts") == "gemini-3.1-flash-tts-preview"
        assert reg.resolve("tts_pro") == "gemini-2.5-pro-preview-tts"

    def test_future_model_is_picked_up_without_code_change(self):
        """The whole point: gemini-4.0-flash appears → it wins, no release needed."""
        reg = _make_registry(LIVE_SNAPSHOT + ["gemini-4.0-flash"])
        assert reg.resolve("text_flash") == "gemini-4.0-flash"

    def test_explain_reports_auto_source_and_ranked_candidates(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        res = reg.explain("text_flash")
        assert res.source == "auto"
        assert res.candidates[:3] == ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]

    def test_autodetect_disabled_uses_fallback_list(self, monkeypatch):
        monkeypatch.setattr(app_config, "model_autodetect", False)
        reg = _make_registry(LIVE_SNAPSHOT)
        res = reg.explain("text_flash")
        assert res.source == "fallback"
        assert res.model == CATEGORY_SPECS["text_flash"].fallbacks[0]


class TestEnvOverride:
    def test_env_override_wins_over_autodetect(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL_FLASH", "gemini-2.5-flash")
        reg = _make_registry(LIVE_SNAPSHOT)
        res = reg.explain("text_flash")
        assert res.model == "gemini-2.5-flash"
        assert res.source == "env"

    def test_env_override_is_not_validated_against_api(self, monkeypatch):
        """An explicit choice is the user's call, even if the API doesn't list it."""
        monkeypatch.setenv("GEMINI_MODEL_PRO", "gemini-9.9-pro-secret")
        reg = _make_registry(LIVE_SNAPSHOT)
        assert reg.resolve("text_pro") == "gemini-9.9-pro-secret"

    def test_blank_env_var_is_ignored(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL_FLASH", "   ")
        reg = _make_registry(LIVE_SNAPSHOT)
        assert reg.explain("text_flash").source == "auto"


class TestFallbacks:
    def test_autodetect_off_skips_fallbacks_the_api_does_not_expose(self, monkeypatch):
        monkeypatch.setattr(app_config, "model_autodetect", False)
        second = CATEGORY_SPECS["text_flash"].fallbacks[1]
        reg = _make_registry([second, "some-unknown-model"])
        res = reg.explain("text_flash")
        assert res.source == "fallback"
        assert res.model == second

    def test_uses_config_default_when_nothing_matches_and_no_fallback_available(self):
        reg = _make_registry(["some-unknown-model"])
        with pytest.warns(RuntimeWarning, match="No available model found"):
            res = reg.explain("text_pro")
        assert res.source == "config"
        assert res.model == STATIC_FALLBACKS["text_pro"]

    def test_empty_available_list_uses_first_fallback(self):
        """When discovery fails (empty list), use the first fallback candidate."""
        reg = _make_registry([])
        res = reg.explain("text_flash")
        assert res.source == "fallback"
        assert res.model == CATEGORY_SPECS["text_flash"].fallbacks[0]

    def test_unknown_category_uses_last_resort(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        with pytest.warns(RuntimeWarning, match="Unknown category"):
            result = reg.resolve("nonexistent_category")
        assert result == "gemini-2.5-flash"


class TestCache:
    def test_resolved_cache_hit(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        first = reg.resolve("text_pro")
        # Corrupt the available list — should still return cached result
        reg._available_model_names = []
        second = reg.resolve("text_pro")
        assert first == second

    def test_invalidate_clears_resolved_and_names(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        reg.resolve("text_pro")
        assert reg._resolved  # Cache populated
        reg.invalidate_cache()
        assert reg._available_model_names is None
        assert reg._resolved == {}

    def test_stale_cache_triggers_refresh(self):
        reg = ModelRegistry()
        reg._available_model_names = ["gemini-2.5-flash"]
        reg._cache_timestamp = time.time() - 9999  # Expired

        refreshed = []

        def fake_refresh():
            refreshed.append(True)
            reg._available_model_names = ["gemini-3.8-flash"]
            reg._cache_timestamp = time.time()

        reg._refresh_cache = fake_refresh
        assert reg.resolve("text_flash") == "gemini-3.8-flash"
        assert refreshed, "Expected cache refresh on stale TTL"

    def test_failed_discovery_backs_off_instead_of_retrying_every_call(self, monkeypatch):
        import app.services.gemini as gemini_mod
        monkeypatch.setattr(gemini_mod, "_available", False)
        monkeypatch.setattr(gemini_mod, "client", None)
        reg = ModelRegistry()
        reg.resolve("text_flash")
        assert reg._available_model_names == []
        assert reg._cache_ttl == _FAILURE_RETRY_TTL
        assert reg._is_cache_valid()  # no second attempt until the back-off expires


class TestListAvailableAndDeprecated:
    def test_list_available_returns_every_category(self):
        reg = _make_registry(LIVE_SNAPSHOT)
        result = reg.list_available()
        for cat in CATEGORY_SPECS:
            assert cat in result

    def test_no_deprecated_when_all_config_defaults_available(self):
        reg = _make_registry(list(STATIC_FALLBACKS.values()))
        assert reg.check_deprecated() == []
        assert "deprecated_in_config" not in reg.list_available()

    def test_detects_config_default_missing_from_api(self):
        from app.core.config import config
        reg = _make_registry(["gemini-2.5-pro"])  # config.model_pro not listed
        deprecated = reg.check_deprecated()
        assert any(config.model_pro in d for d in deprecated)

    def test_empty_when_discovery_failed(self):
        reg = _make_registry([])
        assert reg.check_deprecated() == []
