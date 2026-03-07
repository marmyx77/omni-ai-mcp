"""
Unit tests for ask_model tool (v4.0.0)

Tests provider routing, model resolution, and error handling.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.tools.text.ask_model import _is_gemini_model, _resolve_gemini_model


class TestIsGeminiModel:
    def test_gemini_prefix(self):
        assert _is_gemini_model("gemini-3.1-pro-preview") is True

    def test_models_prefix(self):
        assert _is_gemini_model("models/gemini-2.5-flash") is True

    def test_veo_prefix(self):
        assert _is_gemini_model("veo-3.1-generate-preview") is True

    def test_imagen_prefix(self):
        assert _is_gemini_model("imagen-3.0-generate-002") is True

    def test_deep_research_prefix(self):
        assert _is_gemini_model("deep-research-pro-preview") is True

    def test_short_pro_is_gemini(self):
        assert _is_gemini_model("pro") is True

    def test_short_flash_is_gemini(self):
        assert _is_gemini_model("flash") is True

    def test_short_fast_is_gemini(self):
        assert _is_gemini_model("fast") is True

    def test_openai_is_not_gemini(self):
        assert _is_gemini_model("openai/gpt-4o") is False

    def test_llama_is_not_gemini(self):
        assert _is_gemini_model("meta-llama/llama-3.3-70b") is False

    def test_claude_via_openrouter_is_not_gemini(self):
        assert _is_gemini_model("anthropic/claude-3.5-sonnet") is False


class TestResolveGeminiModel:
    def test_short_pro_resolved(self):
        result = _resolve_gemini_model("pro")
        assert "gemini" in result.lower()

    def test_short_flash_resolved(self):
        result = _resolve_gemini_model("flash")
        assert "gemini" in result.lower()

    def test_short_fast_resolves_flash(self):
        result = _resolve_gemini_model("fast")
        assert "gemini" in result.lower()

    def test_full_id_passthrough(self):
        full_id = "gemini-3.1-pro-preview"
        assert _resolve_gemini_model(full_id) == full_id


class TestAskModelRouting:
    """Test provider routing logic without real API calls.

    ask_model uses local imports inside the function body, so we patch
    the source modules (app.services.*) rather than app.tools.text.ask_model.
    """

    def _mock_gemini(self, response_text: str):
        mock_resp = MagicMock()
        mock_resp.text = response_text
        return mock_resp

    def test_gemini_model_routes_to_gemini(self):
        from app.tools.text.ask_model import ask_model

        mock_resp = self._mock_gemini("Hello from Gemini")

        with patch("app.tools.text.ask_model.generate_with_fallback", return_value=mock_resp), \
             patch("app.tools.text.ask_model.is_available", return_value=True):
            result = ask_model(prompt="hello", model="gemini-3.1-pro-preview")

        assert result == "Hello from Gemini"

    def test_openrouter_model_routes_to_openrouter(self):
        from app.tools.text.ask_model import ask_model

        mock_or = MagicMock()
        mock_or.is_available = True
        mock_or.generate.return_value = "Hello from GPT-4o"
        mock_or._default_model = "openai/gpt-4o"

        with patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(prompt="hello", model="openai/gpt-4o")

        mock_or.generate.assert_called_once()
        assert result == "Hello from GPT-4o"

    def test_openrouter_unavailable_returns_error(self):
        from app.tools.text.ask_model import ask_model

        mock_or = MagicMock()
        mock_or.is_available = False

        with patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(prompt="hello", model="openai/gpt-4o")

        assert "OPENROUTER_API_KEY" in result

    def test_gemini_unavailable_returns_error(self):
        from app.tools.text.ask_model import ask_model

        with patch("app.tools.text.ask_model.is_available", return_value=False), \
             patch("app.tools.text.ask_model.get_error", return_value="No API key"):
            result = ask_model(prompt="hello", model="gemini-2.5-flash")

        assert "No API key" in result or "Error" in result

    def test_gemini_model_overrides_openrouter_provider(self):
        """Gemini model ID always uses Gemini API, even if provider='openrouter' is forced."""
        from app.tools.text.ask_model import ask_model

        mock_resp = self._mock_gemini("Gemini wins")
        mock_or = MagicMock()

        with patch("app.tools.text.ask_model.generate_with_fallback", return_value=mock_resp), \
             patch("app.tools.text.ask_model.is_available", return_value=True), \
             patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(
                prompt="hello", model="gemini-3.1-pro-preview", provider="openrouter"
            )

        mock_or.generate.assert_not_called()
        assert result == "Gemini wins"

    def test_short_name_overrides_openrouter_provider(self):
        """Short alias 'pro' always uses Gemini API, even if provider='openrouter'."""
        from app.tools.text.ask_model import ask_model

        mock_resp = self._mock_gemini("Gemini Pro")
        mock_or = MagicMock()

        with patch("app.tools.text.ask_model.generate_with_fallback", return_value=mock_resp), \
             patch("app.tools.text.ask_model.is_available", return_value=True), \
             patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(prompt="hello", model="pro", provider="openrouter")

        mock_or.generate.assert_not_called()
        assert result == "Gemini Pro"

    def test_provider_gemini_with_non_gemini_model_returns_error(self):
        """provider='gemini' + non-Gemini model → error message."""
        from app.tools.text.ask_model import ask_model

        result = ask_model(prompt="hello", model="openai/gpt-4o", provider="gemini")

        assert "Error" in result
        assert "not a Gemini model" in result

    def test_openrouter_with_no_model_uses_default(self):
        """provider='openrouter' + no model → OpenRouter with default model."""
        from app.tools.text.ask_model import ask_model

        mock_or = MagicMock()
        mock_or.is_available = True
        mock_or.generate.return_value = "OR default"
        mock_or._default_model = "openai/gpt-4o"

        with patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(prompt="hello", model=None, provider="openrouter")

        mock_or.generate.assert_called_once()
        assert result == "OR default"

    def test_auto_provider_none_model_uses_gemini(self):
        from app.tools.text.ask_model import ask_model

        mock_resp = self._mock_gemini("Default Gemini")

        with patch("app.tools.text.ask_model.generate_with_fallback", return_value=mock_resp), \
             patch("app.tools.text.ask_model.is_available", return_value=True):
            result = ask_model(prompt="hello", model=None)

        assert result == "Default Gemini"

    def test_gemini_model_fallback_to_openrouter_when_no_gemini_key(self):
        """No GEMINI_API_KEY → fall back to OpenRouter with google/ prefix."""
        from app.tools.text.ask_model import ask_model

        mock_or = MagicMock()
        mock_or.is_available = True
        mock_or.generate.return_value = "Google via OpenRouter"

        with patch("app.tools.text.ask_model.is_available", return_value=False), \
             patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(prompt="hello", model="gemini-2.5-flash")

        mock_or.generate.assert_called_once()
        call_kwargs = mock_or.generate.call_args
        assert call_kwargs.kwargs["model"] == "google/gemini-2.5-flash"
        assert result == "Google via OpenRouter"

    def test_gemini_model_no_keys_returns_error(self):
        """No GEMINI_API_KEY and no OPENROUTER_API_KEY → clear error."""
        from app.tools.text.ask_model import ask_model

        mock_or = MagicMock()
        mock_or.is_available = False

        with patch("app.tools.text.ask_model.is_available", return_value=False), \
             patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(prompt="hello", model="gemini-2.5-flash")

        assert "Error" in result
        assert "API key" in result

    def test_veo_model_no_openrouter_fallback(self):
        """veo- models have no OpenRouter equivalent → error even with OpenRouter key."""
        from app.tools.text.ask_model import ask_model

        mock_or = MagicMock()
        mock_or.is_available = True

        with patch("app.tools.text.ask_model.is_available", return_value=False), \
             patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(prompt="make video", model="veo-3.1-generate-preview")

        mock_or.generate.assert_not_called()
        assert "Error" in result
        assert "GEMINI_API_KEY" in result

    def test_openrouter_model_no_key_returns_error(self):
        """Non-Gemini model + no OpenRouter key → clear error."""
        from app.tools.text.ask_model import ask_model

        mock_or = MagicMock()
        mock_or.is_available = False

        with patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(prompt="hello", model="openai/gpt-4o")

        assert "OPENROUTER_API_KEY" in result


class TestToOpenrouterGoogleId:
    def test_gemini_prefix_maps_correctly(self):
        from app.tools.text.ask_model import _to_openrouter_google_id
        assert _to_openrouter_google_id("gemini-2.5-flash") == "google/gemini-2.5-flash"
        assert _to_openrouter_google_id("gemini-3.1-pro-preview") == "google/gemini-3.1-pro-preview"

    def test_models_prefix_stripped(self):
        from app.tools.text.ask_model import _to_openrouter_google_id
        assert _to_openrouter_google_id("models/gemini-2.5-flash") == "google/gemini-2.5-flash"

    def test_veo_returns_none(self):
        from app.tools.text.ask_model import _to_openrouter_google_id
        assert _to_openrouter_google_id("veo-3.1-generate-preview") is None

    def test_imagen_returns_none(self):
        from app.tools.text.ask_model import _to_openrouter_google_id
        assert _to_openrouter_google_id("imagen-3.0-generate-002") is None

    def test_deep_research_returns_none(self):
        from app.tools.text.ask_model import _to_openrouter_google_id
        assert _to_openrouter_google_id("deep-research-pro-preview") is None

    def test_short_names_return_none(self):
        from app.tools.text.ask_model import _to_openrouter_google_id
        assert _to_openrouter_google_id("pro") is None
        assert _to_openrouter_google_id("flash") is None


class TestListModels:
    def test_returns_string(self):
        from app.tools.text.models import list_models
        from app.services.model_registry import ModelRegistry
        import time

        fake_reg = ModelRegistry()
        fake_reg._available_model_names = ["gemini-3.1-pro-preview", "gemini-2.5-flash",
                                            "gemini-2.5-flash-lite", "veo-3.1-generate-preview",
                                            "gemini-2.5-flash-preview-tts"]
        fake_reg._cache_timestamp = time.time()

        mock_or = MagicMock()
        mock_or.is_available = False

        with patch("app.tools.text.models.model_registry", fake_reg), \
             patch("app.tools.text.models.openrouter_client", mock_or):
            result = list_models(include_openrouter=True)

        assert isinstance(result, str)
        assert "Text Pro" in result

    def test_openrouter_section_when_available(self):
        from app.tools.text.models import list_models
        from app.services.model_registry import ModelRegistry
        import time

        fake_reg = ModelRegistry()
        fake_reg._available_model_names = ["gemini-2.5-flash"]
        fake_reg._cache_timestamp = time.time()

        mock_or = MagicMock()
        mock_or.is_available = True
        mock_or.list_model_ids.return_value = ["openai/gpt-4o", "meta-llama/llama-3.3-70b"]

        with patch("app.tools.text.models.model_registry", fake_reg), \
             patch("app.tools.text.models.openrouter_client", mock_or):
            result = list_models(include_openrouter=True)

        assert "OpenRouter" in result

    def test_openrouter_not_configured_message(self):
        from app.tools.text.models import list_models
        from app.services.model_registry import ModelRegistry
        import time

        fake_reg = ModelRegistry()
        fake_reg._available_model_names = ["gemini-2.5-flash"]
        fake_reg._cache_timestamp = time.time()

        mock_or = MagicMock()
        mock_or.is_available = False

        with patch("app.tools.text.models.model_registry", fake_reg), \
             patch("app.tools.text.models.openrouter_client", mock_or):
            result = list_models(include_openrouter=True)

        assert "OPENROUTER_API_KEY" in result
