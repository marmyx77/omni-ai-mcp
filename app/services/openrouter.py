"""
OpenRouter Multi-Provider Client

Optional integration for 400+ AI models via OpenRouter API.
Requires OPENROUTER_API_KEY environment variable — silently disabled if absent.
"""

import json
import time
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from ..core import config, log_progress


_BASE_URL = "https://openrouter.ai/api/v1"
_MODELS_CACHE_TTL = 3600  # 1 hour


class OpenRouterClient:
    """
    Client for OpenRouter API (OpenAI-compatible).

    All methods silently return empty results when the API key is not configured.
    """

    def __init__(self, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._models_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: float = 0.0

    @property
    def is_available(self) -> bool:
        """True if an API key is configured."""
        return bool(self._api_key)

    def _request(self, path: str, payload: Optional[Dict] = None) -> Any:
        """Perform a JSON HTTP request to OpenRouter."""
        url = f"{_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/omni-ai-mcp",
            "X-Title": "omni-ai-mcp",
        }
        data = json.dumps(payload).encode() if payload else None
        req = Request(url, data=data, headers=headers, method="POST" if payload else "GET")

        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def list_models(self) -> List[Dict[str, Any]]:
        """List available models (cached for 1 hour)."""
        if not self.is_available:
            return []

        if (
            self._models_cache is not None
            and (time.time() - self._cache_timestamp) < _MODELS_CACHE_TTL
        ):
            return self._models_cache

        try:
            data = self._request("/models")
            models = data.get("data", [])
            self._models_cache = models
            self._cache_timestamp = time.time()
            log_progress(f"openrouter: {len(models)} models available")
            return models
        except (URLError, HTTPError, Exception) as e:
            log_progress(f"openrouter: list_models failed ({e})")
            return []

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
            choices = result.get("choices", [])
            if not choices:
                return "Error: No response from OpenRouter"
            return choices[0]["message"]["content"]
        except HTTPError as e:
            body = e.read().decode() if hasattr(e, "read") else ""
            return f"Error: OpenRouter HTTP {e.code}: {body}"
        except Exception as e:
            return f"Error: OpenRouter request failed: {e}"

    def is_gemini_model(self, model_id: str) -> bool:
        """Return True if the model ID belongs to Google/Gemini."""
        gemini_prefixes = ("gemini-", "models/gemini-")
        return any(model_id.lower().startswith(p) for p in gemini_prefixes)


# Global client instance (disabled when OPENROUTER_API_KEY not set)
openrouter_client = OpenRouterClient(
    api_key=config.openrouter_api_key,
    default_model=config.openrouter_default_model,
)
