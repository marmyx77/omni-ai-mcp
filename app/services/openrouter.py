"""
OpenRouter Multi-Provider Client

Optional integration for 400+ AI models via OpenRouter API.
Requires OPENROUTER_API_KEY environment variable — silently disabled if absent.
"""

import json
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from ..core import config, log_progress
from ..core.security import secrets_sanitizer


_BASE_URL = "https://openrouter.ai/api/v1"
_MODELS_CACHE_TTL = 3600  # 1 hour
_DEFAULT_TIMEOUT = 120  # seconds — search models (e.g. perplexity/sonar-*) need headroom
_METADATA_TIMEOUT = 30  # seconds — fast endpoints like /models
_LIST_FAILURE_BACKOFF = 300  # seconds before retrying a failed /models call
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})  # GET (idempotent)
# A generation (POST) is retried only when it surely did not run: rate limited or
# service unavailable. A 500/502/504 or a timeout may have been processed and billed.
_POST_RETRY_STATUSES = frozenset({429, 503})
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.0  # seconds, doubled per attempt
_MAX_RETRY_DELAY = 10.0  # cap on Retry-After / backoff
_MAX_ERROR_BODY = 500  # characters of an error body shown to the user
_MODEL_HINT = "Check the ID with gemini_list_models(include_openrouter=True)."


def _retry_delay(attempt: int, retry_after: Optional[str]) -> float:
    """Seconds to wait before retry `attempt` (0-based): Retry-After if numeric, else backoff."""
    try:
        if retry_after is not None:
            return min(max(float(retry_after), 0.0), _MAX_RETRY_DELAY)
    except ValueError:
        pass
    return min(_RETRY_BASE_DELAY * (2 ** attempt), _MAX_RETRY_DELAY)


def _clean_error_text(text: str) -> str:
    """Short, secret-free version of an upstream error body."""
    text = " ".join(str(text).split())
    if len(text) > _MAX_ERROR_BODY:
        text = text[:_MAX_ERROR_BODY] + "…"
    return secrets_sanitizer.sanitize(text)


def _error_message(body: str) -> str:
    """Pull `error.message` out of an OpenRouter JSON error body, else the raw body."""
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return body
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return body


def _extract_citations(result: Dict[str, Any]) -> List[str]:
    """
    Collect citation URLs from an OpenRouter chat completion response.

    Supports both formats:
    - Top-level "citations" list of URL strings (Perplexity sonar models)
    - OpenAI-style "annotations" with url_citation objects in the message

    Returns:
        Deduplicated list of URLs, original order preserved
    """
    top_level = [
        url for url in (result.get("citations") or [])
        if isinstance(url, str) and url
    ]

    choices = result.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    annotated = [
        (ann.get("url_citation") or {}).get("url", "")
        for ann in (message.get("annotations") or [])
        if isinstance(ann, dict) and ann.get("type") == "url_citation"
    ]

    return list(dict.fromkeys(url for url in top_level + annotated if url))


def _append_sources(text: str, citations: List[str]) -> str:
    """Return text with a numbered Sources section appended (unchanged if no citations)."""
    if not citations:
        return text
    sources = "\n".join(f"{i}. {url}" for i, url in enumerate(citations, 1))
    return f"{text}\n\n---\n**Sources:**\n{sources}"


class OpenRouterClient:
    """
    Client for OpenRouter API (OpenAI-compatible).

    All methods silently return empty results when the API key is not configured.
    """

    def __init__(
        self,
        api_key: str,
        default_model: str,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._timeout = timeout
        self._models_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: float = 0.0
        self._list_failed_at: float = 0.0
        self._sleep: Callable[[float], None] = time.sleep  # injectable for tests

    @property
    def default_model(self) -> str:
        """Model used when no model ID is given (OPENROUTER_DEFAULT_MODEL)."""
        return self._default_model

    @property
    def is_available(self) -> bool:
        """True if an API key is configured."""
        return bool(self._api_key)

    def _request(
        self,
        path: str,
        payload: Optional[Dict] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """Perform a JSON HTTP request to OpenRouter."""
        url = f"{_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/omni-ai-mcp",
            "X-Title": "omni-ai-mcp",
        }
        data = json.dumps(payload).encode() if payload else None
        retry_statuses = _POST_RETRY_STATUSES if payload else _RETRY_STATUSES

        for attempt in range(_MAX_RETRIES + 1):
            req = Request(url, data=data, headers=headers, method="POST" if payload else "GET")
            try:
                with urlopen(req, timeout=timeout or self._timeout) as resp:
                    return json.loads(resp.read().decode())
            except HTTPError as e:
                if e.code not in retry_statuses or attempt == _MAX_RETRIES:
                    raise
                delay = _retry_delay(attempt, e.headers.get("Retry-After") if e.headers else None)
                log_progress(f"openrouter: HTTP {e.code}, retry {attempt + 1}/{_MAX_RETRIES} in {delay:.1f}s")
            except URLError as e:
                timed_out = isinstance(e.reason, TimeoutError)
                if attempt == _MAX_RETRIES or (payload and timed_out):
                    raise
                delay = _retry_delay(attempt, None)
                log_progress(f"openrouter: network error ({e.reason}), retry {attempt + 1}/{_MAX_RETRIES} in {delay:.1f}s")
            self._sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover

    def list_models(self) -> List[Dict[str, Any]]:
        """List available models (cached for 1 hour)."""
        if not self.is_available:
            return []

        now = time.time()
        if self._models_cache is not None and (now - self._cache_timestamp) < _MODELS_CACHE_TTL:
            return self._models_cache
        if self._list_failed_at and (now - self._list_failed_at) < _LIST_FAILURE_BACKOFF:
            return self._models_cache or []

        try:
            data = self._request("/models", timeout=_METADATA_TIMEOUT)
            models = data.get("data", [])
            self._models_cache = models
            self._cache_timestamp = time.time()
            self._list_failed_at = 0.0
            log_progress(f"openrouter: {len(models)} models available")
            return models
        except Exception as e:
            self._list_failed_at = time.time()
            log_progress(f"openrouter: list_models failed ({_clean_error_text(e)})")
            return self._models_cache or []

    def list_model_ids(self) -> List[str]:
        """Return sorted list of model IDs."""
        return sorted(m.get("id", "") for m in self.list_models() if m.get("id"))

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text via OpenRouter chat completions.

        Args:
            prompt: User message
            model: Model ID (e.g. "openai/gpt-4o"), uses default_model if omitted
            system_prompt: Optional system message
            temperature: Sampling temperature 0-2

        Returns:
            Generated text or error message
        """
        if not self.is_available:
            return "Error: OPENROUTER_API_KEY not configured"

        selected_model = model or self._default_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            log_progress(f"openrouter: Generating with {selected_model}")
            result = self._request("/chat/completions", payload)
        except HTTPError as e:
            return self._http_error(e, selected_model)
        except Exception as e:
            return f"Error: OpenRouter request failed: {_clean_error_text(e)}"
        return self._parse_completion(result, selected_model)

    @staticmethod
    def _http_error(e: HTTPError, model: str) -> str:
        """User-facing message for an HTTP error, with a hint for unknown models."""
        try:
            body = e.read().decode(errors="replace")
        except Exception:
            body = ""
        message = _clean_error_text(_error_message(body)) or e.reason
        hint = f" {_MODEL_HINT}" if e.code in (400, 404) and "model" in message.lower() else ""
        return f"Error: OpenRouter HTTP {e.code} for '{model}': {message}{hint}"

    @staticmethod
    def _parse_completion(result: Any, model: str) -> str:
        """Text of a chat completion, or an explicit error (errors can arrive with HTTP 200)."""
        if not isinstance(result, dict):
            return f"Error: unexpected OpenRouter response for '{model}'"
        error = result.get("error")
        if error:
            message = error.get("message") if isinstance(error, dict) else error
            return f"Error: OpenRouter error for '{model}': {_clean_error_text(message)}"
        choices = result.get("choices") or []
        if not choices:
            return f"Error: No response from '{model}' on OpenRouter"
        message = choices[0].get("message") or {}
        text = message.get("content")
        if not text or not str(text).strip():
            reason = choices[0].get("finish_reason") or "unknown"
            return f"Error: empty response from '{model}' (finish_reason: {reason})"
        return _append_sources(str(text), _extract_citations(result))

    def is_gemini_model(self, model_id: str) -> bool:
        """Return True if the model ID belongs to Google/Gemini."""
        gemini_prefixes = ("gemini-", "models/gemini-")
        return any(model_id.lower().startswith(p) for p in gemini_prefixes)


# Global client instance (disabled when OPENROUTER_API_KEY not set)
openrouter_client = OpenRouterClient(
    api_key=config.openrouter_api_key,
    default_model=config.openrouter_default_model,
    timeout=config.openrouter_timeout,
)
