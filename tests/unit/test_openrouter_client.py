"""
Unit tests for OpenRouterClient (v4.0.0)

Tests availability check, model listing, generation routing,
and error handling — without real HTTP calls.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from urllib.error import HTTPError

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.openrouter import OpenRouterClient


def _client(key: str = "sk-or-test") -> OpenRouterClient:
    return OpenRouterClient(api_key=key, default_model="openai/gpt-4o")


class TestAvailability:
    def test_available_when_key_set(self):
        assert _client("sk-or-test").is_available is True

    def test_not_available_when_key_empty(self):
        assert _client("").is_available is False

    def test_generate_returns_error_when_unavailable(self):
        c = _client("")
        result = c.generate("hello")
        assert "OPENROUTER_API_KEY" in result


class TestListModels:
    def test_returns_empty_when_no_key(self):
        c = _client("")
        assert c.list_models() == []

    def test_returns_cached_on_second_call(self):
        c = _client("key")
        fake_models = [{"id": "openai/gpt-4o"}, {"id": "meta-llama/llama-3.3-70b"}]

        with patch.object(c, "_request", return_value={"data": fake_models}) as mock_req:
            first = c.list_models()
            second = c.list_models()

        assert first == fake_models
        assert second == fake_models
        mock_req.assert_called_once()  # Second call hits cache

    def test_returns_empty_on_request_error(self):
        c = _client("key")
        with patch.object(c, "_request", side_effect=Exception("network error")):
            result = c.list_models()
        assert result == []

    def test_list_model_ids_returns_sorted(self):
        c = _client("key")
        fake_models = [{"id": "z-model"}, {"id": "a-model"}, {"id": "m-model"}]
        with patch.object(c, "list_models", return_value=fake_models):
            ids = c.list_model_ids()
        assert ids == ["a-model", "m-model", "z-model"]

    def test_list_model_ids_skips_missing_id(self):
        c = _client("key")
        fake_models = [{"id": "good-model"}, {"name": "no-id-model"}]
        with patch.object(c, "list_models", return_value=fake_models):
            ids = c.list_model_ids()
        assert "good-model" in ids
        assert "" not in ids


class TestGenerate:
    def _fake_response(self, content: str) -> dict:
        return {"choices": [{"message": {"content": content}}]}

    def test_returns_model_response(self):
        c = _client("key")
        with patch.object(c, "_request", return_value=self._fake_response("Hello!")):
            result = c.generate("hi")
        assert result == "Hello!"

    def test_uses_default_model_when_none(self):
        c = _client("key")
        captured = {}

        def capture(path, payload):
            captured["model"] = payload["model"]
            return self._fake_response("ok")

        with patch.object(c, "_request", side_effect=capture):
            c.generate("hi", model=None)
        assert captured["model"] == "openai/gpt-4o"

    def test_uses_specified_model(self):
        c = _client("key")
        captured = {}

        def capture(path, payload):
            captured["model"] = payload["model"]
            return self._fake_response("ok")

        with patch.object(c, "_request", side_effect=capture):
            c.generate("hi", model="meta-llama/llama-3.3-70b")
        assert captured["model"] == "meta-llama/llama-3.3-70b"

    def test_includes_system_prompt(self):
        c = _client("key")
        captured = {}

        def capture(path, payload):
            captured["messages"] = payload["messages"]
            return self._fake_response("ok")

        with patch.object(c, "_request", side_effect=capture):
            c.generate("hi", system_prompt="You are helpful")

        roles = [m["role"] for m in captured["messages"]]
        assert roles[0] == "system"
        assert roles[1] == "user"

    def test_no_system_message_when_not_provided(self):
        c = _client("key")
        captured = {}

        def capture(path, payload):
            captured["messages"] = payload["messages"]
            return self._fake_response("ok")

        with patch.object(c, "_request", side_effect=capture):
            c.generate("hi")

        roles = [m["role"] for m in captured["messages"]]
        assert "system" not in roles

    def test_returns_error_string_on_exception(self):
        c = _client("key")
        with patch.object(c, "_request", side_effect=Exception("timeout")):
            result = c.generate("hi")
        assert "Error" in result

    def test_returns_error_on_empty_choices(self):
        c = _client("key")
        with patch.object(c, "_request", return_value={"choices": []}):
            result = c.generate("hi")
        assert "No response" in result


class TestIsGeminiModel:
    def test_detects_gemini_prefix(self):
        c = _client()
        assert c.is_gemini_model("gemini-3.1-pro-preview") is True

    def test_detects_models_prefix(self):
        c = _client()
        assert c.is_gemini_model("models/gemini-2.5-flash") is True

    def test_non_gemini_returns_false(self):
        c = _client()
        assert c.is_gemini_model("openai/gpt-4o") is False
        assert c.is_gemini_model("meta-llama/llama-3.3-70b") is False


def _mock_urlopen(response_dict: dict) -> MagicMock:
    """Build a context-manager mock for urlopen returning the given JSON."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(response_dict).encode()
    cm = MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


_COMPLETION_BASE = {"choices": [{"message": {"content": "Answer text"}}]}


class TestConfigurableTimeout:
    def test_default_timeout_is_120(self):
        assert _client()._timeout == 120

    def test_custom_timeout_stored(self):
        c = OpenRouterClient(api_key="k", default_model="openai/gpt-4o", timeout=300)
        assert c._timeout == 300

    def test_generate_uses_configured_timeout(self):
        c = OpenRouterClient(api_key="k", default_model="openai/gpt-4o", timeout=300)
        with patch(
            "app.services.openrouter.urlopen",
            return_value=_mock_urlopen(_COMPLETION_BASE),
        ) as mock_open:
            c.generate("hi")
        assert mock_open.call_args.kwargs["timeout"] == 300

    def test_list_models_uses_short_timeout(self):
        """Model catalog is fast metadata — must not inherit the long generation timeout."""
        c = OpenRouterClient(api_key="k", default_model="openai/gpt-4o", timeout=300)
        with patch(
            "app.services.openrouter.urlopen",
            return_value=_mock_urlopen({"data": []}),
        ) as mock_open:
            c.list_models()
        assert mock_open.call_args.kwargs["timeout"] == 30

    def test_config_env_var_read(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_TIMEOUT", "240")
        from app.core.config import Config

        assert Config().openrouter_timeout == 240

    def test_config_default_120(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_TIMEOUT", raising=False)
        from app.core.config import Config

        assert Config().openrouter_timeout == 120


class TestExtractCitations:
    def test_no_citations_returns_empty(self):
        from app.services.openrouter import _extract_citations

        assert _extract_citations(_COMPLETION_BASE) == []

    def test_top_level_citations(self):
        from app.services.openrouter import _extract_citations

        result = {**_COMPLETION_BASE, "citations": ["https://a.com", "https://b.com"]}
        assert _extract_citations(result) == ["https://a.com", "https://b.com"]

    def test_message_annotations_url_citation(self):
        from app.services.openrouter import _extract_citations

        result = {
            "choices": [{
                "message": {
                    "content": "x",
                    "annotations": [
                        {"type": "url_citation", "url_citation": {"url": "https://c.com"}},
                        {"type": "other", "url_citation": {"url": "https://ignored.com"}},
                    ],
                }
            }]
        }
        assert _extract_citations(result) == ["https://c.com"]

    def test_dedupe_preserves_order(self):
        from app.services.openrouter import _extract_citations

        result = {
            "citations": ["https://a.com", "https://b.com", "https://a.com"],
            "choices": [{
                "message": {
                    "content": "x",
                    "annotations": [
                        {"type": "url_citation", "url_citation": {"url": "https://b.com"}},
                        {"type": "url_citation", "url_citation": {"url": "https://c.com"}},
                    ],
                }
            }],
        }
        assert _extract_citations(result) == [
            "https://a.com", "https://b.com", "https://c.com"
        ]

    def test_malformed_entries_skipped(self):
        from app.services.openrouter import _extract_citations

        result = {
            "citations": [None, 42, "", "https://ok.com"],
            "choices": [{
                "message": {
                    "content": "x",
                    "annotations": ["not-a-dict", {"type": "url_citation"}],
                }
            }],
        }
        assert _extract_citations(result) == ["https://ok.com"]


class TestGenerateWithCitations:
    def test_citations_appended_as_sources(self):
        c = _client()
        response = {**_COMPLETION_BASE, "citations": ["https://a.com", "https://b.com"]}
        with patch.object(c, "_request", return_value=response):
            result = c.generate("hi")
        assert result.startswith("Answer text")
        assert "**Sources:**" in result
        assert "1. https://a.com" in result
        assert "2. https://b.com" in result

    def test_no_citations_returns_plain_text(self):
        c = _client()
        with patch.object(c, "_request", return_value=_COMPLETION_BASE):
            result = c.generate("hi")
        assert result == "Answer text"
