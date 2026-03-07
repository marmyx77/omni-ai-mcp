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

    def test_provider_force_openrouter(self):
        from app.tools.text.ask_model import ask_model

        mock_or = MagicMock()
        mock_or.is_available = True
        mock_or.generate.return_value = "Forced OR"
        mock_or._default_model = "openai/gpt-4o"

        with patch("app.tools.text.ask_model.openrouter_client", mock_or):
            result = ask_model(
                prompt="hello", model="gemini-3.1-pro-preview", provider="openrouter"
            )

        mock_or.generate.assert_called_once()
        assert result == "Forced OR"

    def test_auto_provider_none_model_uses_gemini(self):
        from app.tools.text.ask_model import ask_model

        mock_resp = self._mock_gemini("Default Gemini")

        with patch("app.tools.text.ask_model.generate_with_fallback", return_value=mock_resp), \
             patch("app.tools.text.ask_model.is_available", return_value=True):
            result = ask_model(prompt="hello", model=None)

        assert result == "Default Gemini"


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
