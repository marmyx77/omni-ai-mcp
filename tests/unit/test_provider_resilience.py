"""
Provider resilience (v4.8.2): OpenRouter retries and error handling, ask_model
routing rules, Gemini quota detection and fallback, registry flagship pattern
and thread safety. All hermetic: no network, no API key.
"""

import io
import json
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.openrouter import OpenRouterClient, _retry_delay


def _client() -> OpenRouterClient:
    c = OpenRouterClient(api_key="sk-or-test", default_model="openai/gpt-4o", timeout=5)
    c._sleep = lambda _s: None
    return c


def _http_error(code: int, body: str = "", headers=None) -> HTTPError:
    return HTTPError("https://openrouter.ai/api/v1/x", code, "err", headers or {}, io.BytesIO(body.encode()))


def _ok(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


COMPLETION = {"choices": [{"message": {"content": "hi"}}]}


class TestOpenRouterRetry:
    def test_retries_transient_status_then_succeeds(self):
        c = _client()
        with patch("app.services.openrouter.urlopen",
                   side_effect=[_http_error(503), _http_error(429), _ok(COMPLETION)]) as op:
            assert c.generate("q") == "hi"
        assert op.call_count == 3

    def test_gives_up_after_max_retries(self):
        c = _client()
        with patch("app.services.openrouter.urlopen", side_effect=[_http_error(503)] * 3) as op:
            assert c.generate("q").startswith("Error: OpenRouter HTTP 503")
        assert op.call_count == 3

    def test_generation_not_resent_after_possibly_processed_error(self):
        """A 502 on a POST may have run (and been billed): no retry."""
        c = _client()
        with patch("app.services.openrouter.urlopen", side_effect=[_http_error(502), _ok(COMPLETION)]) as op:
            assert c.generate("q").startswith("Error: OpenRouter HTTP 502")
        assert op.call_count == 1

    def test_generation_not_resent_after_timeout(self):
        c = _client()
        with patch("app.services.openrouter.urlopen", side_effect=[URLError(TimeoutError("read")), _ok(COMPLETION)]) as op:
            assert c.generate("q").startswith("Error: OpenRouter request failed")
        assert op.call_count == 1

    def test_model_listing_retries_server_errors(self):
        c = _client()
        with patch("app.services.openrouter.urlopen", side_effect=[_http_error(502), _ok({"data": [{"id": "a/b"}]})]):
            assert c.list_model_ids() == ["a/b"]

    def test_no_retry_on_client_error(self):
        c = _client()
        with patch("app.services.openrouter.urlopen", side_effect=[_http_error(401, '{"error":{"message":"bad key"}}')]) as op:
            result = c.generate("q")
        assert op.call_count == 1 and "bad key" in result

    def test_network_error_is_retried(self):
        c = _client()
        with patch("app.services.openrouter.urlopen", side_effect=[URLError("reset"), _ok(COMPLETION)]):
            assert c.generate("q") == "hi"

    def test_retry_delay_honours_retry_after_with_cap(self):
        assert _retry_delay(0, "2") == 2.0
        assert _retry_delay(0, "600") == 10.0
        assert _retry_delay(1, None) == 2.0
        assert _retry_delay(0, "soon") == 1.0


class TestOpenRouterErrors:
    def test_unknown_model_gets_a_hint(self):
        c = _client()
        body = '{"error":{"message":"foo/bar is not a valid model ID"}}'
        with patch("app.services.openrouter.urlopen", side_effect=[_http_error(400, body)]):
            result = c.generate("q", model="foo/bar")
        assert "not a valid model ID" in result and "gemini_list_models" in result

    def test_error_body_is_sanitized_and_truncated(self):
        c = _client()
        body = "leaked AIzaSyA" + "x" * 35 + " " + "y" * 2000
        with patch("app.services.openrouter.urlopen", side_effect=[_http_error(400, body)]):
            result = c.generate("q")
        assert "AIzaSy" not in result and len(result) < 800

    def test_error_inside_a_200_response(self):
        c = _client()
        with patch.object(c, "_request", return_value={"error": {"message": "provider overloaded"}}):
            assert "provider overloaded" in c.generate("q")

    @pytest.mark.parametrize("content", [None, "", "   "])
    def test_empty_content_is_an_error(self, content):
        c = _client()
        result_payload = {"choices": [{"message": {"content": content}, "finish_reason": "content_filter"}]}
        with patch.object(c, "_request", return_value=result_payload):
            result = c.generate("q")
        assert result.startswith("Error: empty response") and "content_filter" in result

    def test_list_models_failure_backs_off(self):
        c = _client()
        with patch.object(c, "_request", side_effect=RuntimeError("down")) as req:
            assert c.list_models() == []
            assert c.list_models() == []
        assert req.call_count == 1


class TestAskModelRouting:
    def _or(self):
        mock_or = MagicMock(is_available=True, default_model="openai/gpt-4o")
        mock_or.generate.return_value = "OR"
        return mock_or

    def test_empty_model_string_means_default(self):
        from app.tools.text.ask_model import ask_model
        native = MagicMock(return_value=MagicMock(text="G"))
        with patch("app.tools.text.ask_model.generate_with_fallback", native), \
             patch("app.tools.text.ask_model.is_available", return_value=True):
            assert ask_model(prompt="q", model="  ") == "G"

    def test_auto_without_gemini_key_and_no_model_uses_openrouter_default(self):
        from app.tools.text.ask_model import ask_model
        mock_or = self._or()
        with patch("app.tools.text.ask_model.is_available", return_value=False), \
             patch("app.tools.text.ask_model.openrouter_client", mock_or):
            assert ask_model(prompt="q") == "OR"
        assert mock_or.generate.call_args.kwargs["model"] is None  # OPENROUTER_DEFAULT_MODEL

    def test_provider_openrouter_no_model_uses_openrouter_default(self):
        from app.tools.text.ask_model import ask_model
        mock_or = self._or()
        with patch("app.tools.text.ask_model.is_available", return_value=True), \
             patch("app.tools.text.ask_model.openrouter_client", mock_or):
            assert ask_model(prompt="q", provider="openrouter") == "OR"
        assert mock_or.generate.call_args.kwargs["model"] is None

    def test_provider_openrouter_without_key(self):
        from app.tools.text.ask_model import ask_model
        with patch("app.tools.text.ask_model.openrouter_client", MagicMock(is_available=False)):
            assert "OPENROUTER_API_KEY" in ask_model(prompt="q", model="pro", provider="openrouter")

    def test_unknown_provider(self):
        from app.tools.text.ask_model import ask_model
        assert "unknown provider" in ask_model(prompt="q", provider="azure")

    def test_explicit_id_disables_flash_fallback_alias_keeps_it(self):
        from app.tools.text.ask_model import ask_model
        native = MagicMock(return_value=MagicMock(text="G"))
        with patch("app.tools.text.ask_model.generate_with_fallback", native), \
             patch("app.tools.text.ask_model.is_available", return_value=True), \
             patch("app.tools.text.ask_model._resolve_gemini_model", side_effect=lambda m: m if m != "pro" else "gemini-4-argon"):
            ask_model(prompt="q", model="gemini-4-argon")
            assert native.call_args.kwargs["allow_fallback"] is False
            ask_model(prompt="q", model="pro")
            assert native.call_args.kwargs["allow_fallback"] is True

    def test_empty_gemini_text_is_an_error(self):
        from app.tools.text.ask_model import ask_model
        with patch("app.tools.text.ask_model.generate_with_fallback", return_value=MagicMock(text=None)), \
             patch("app.tools.text.ask_model.is_available", return_value=True):
            assert ask_model(prompt="q", model="gemini-4-argon").startswith("Error: empty response")


class TestGeminiQuotaFallback:
    class _ApiError(Exception):
        def __init__(self, message, code=None):
            super().__init__(message)
            self.code = code

    @pytest.mark.parametrize("message,code,expected", [
        ("429 RESOURCE_EXHAUSTED", None, True),
        ("anything", 429, True),
        ("Quota exceeded for metric", None, True),
        ("rate limit reached", None, True),
        ("404 models/x is not found for API version v1beta, or is not supported for generateContent", 404, False),
        ("Your project has exceeded its spending cap", 429, False),
        ("500 internal error while generating", 500, False),
    ])
    def test_is_quota_error(self, message, code, expected):
        from app.services.gemini import is_quota_error
        assert is_quota_error(self._ApiError(message, code)) is expected

    def _run(self, error, allow_fallback=True):
        from app.services import gemini
        fake = MagicMock()
        fake.models.generate_content.side_effect = [error, "flash-response"]
        with patch.object(gemini, "client", fake), patch.object(gemini, "_available", True), \
             patch.object(gemini.model_registry, "resolve", return_value="gemini-3.8-flash"):
            try:
                return gemini.generate_with_fallback("gemini-4-argon", "q", allow_fallback=allow_fallback), fake
            except Exception as e:  # noqa: BLE001 - the test inspects it
                return e, fake

    def test_quota_falls_back_to_flash(self):
        result, fake = self._run(self._ApiError("quota", 429))
        assert result == "flash-response"
        assert fake.models.generate_content.call_args.kwargs["model"] == "gemini-3.8-flash"

    def test_not_found_is_not_masked_by_fallback(self):
        result, fake = self._run(self._ApiError("not supported for generateContent", 404))
        assert isinstance(result, Exception) and fake.models.generate_content.call_count == 1

    def test_allow_fallback_false_raises(self):
        result, fake = self._run(self._ApiError("quota", 429), allow_fallback=False)
        assert isinstance(result, Exception) and fake.models.generate_content.call_count == 1


class TestRegistry:
    @pytest.mark.parametrize("model_id,matches", [
        ("gemini-4-argon", True),
        ("gemini-4.1-argon-preview", True),
        ("gemini-3.1-pro-preview", True),
        ("gemini-2.5-pro", True),
        ("gemini-2.0-exp", False),
        ("gemini-3-thinking", False),
        ("gemini-4-flash", False),
        ("gemini-4-omni", False),
        ("gemini-4-argon-customtools", False),
    ])
    def test_flagship_pattern(self, model_id, matches):
        from app.services.model_registry import CATEGORY_SPECS
        assert (CATEGORY_SPECS["text_pro"].version_key(model_id) is not None) is matches

    def test_concurrent_resolves_list_models_once(self):
        import importlib
        mr = importlib.import_module("app.services.model_registry")
        registry = mr.ModelRegistry()
        calls = []
        gate = threading.Event()

        def slow_list(**_kwargs):
            calls.append(1)
            gate.wait(0.2)
            return [_model("models/gemini-4-argon")]

        fake = MagicMock()
        fake.models.list.side_effect = slow_list
        with patch("app.services.gemini.client", fake), patch("app.services.gemini._available", True), \
             patch.object(mr.config, "model_autodetect", True):
            threads = [threading.Thread(target=registry.resolve, args=("text_pro",)) for _ in range(5)]
            for t in threads:
                t.start()
            gate.set()
            for t in threads:
                t.join(5)
        assert len(calls) == 1
        assert registry.resolve("text_pro") == "gemini-4-argon"


def _model(name: str) -> MagicMock:
    m = MagicMock()
    m.name = name
    m.supported_actions = ["generateContent"]
    return m
