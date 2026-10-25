"""
Multi-Provider Ask Tool (v4.0.0)

Routes requests to Gemini or OpenRouter based on model ID / provider selection.
Enables access to 400+ models beyond Gemini.
"""

from typing import Optional

from ...tools.registry import tool
from ...services.model_registry import CATEGORY_PRIORITIES
from ...services.gemini import generate_with_fallback, types, is_available, get_error, legacy_sampling
from ...services.openrouter import openrouter_client


ASK_MODEL_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "The question or prompt to send"
        },
        "model": {
            "type": "string",
            "description": (
                "Model ID or alias. Gemini aliases: 'pro' (newest flagship, Gemini 4 Argon), 'flash', 'flash-lite'; "
                "explicit IDs like 'gemini-4-argon', 'gemini-3.8-flash'; Gemma 4 open models 'gemma-4-31b-it', 'gemma-4-26b-a4b-it'. "
                "OpenRouter examples: 'openai/gpt-4o', 'meta-llama/llama-3.3-70b', "
                "'anthropic/claude-3.5-sonnet', 'perplexity/sonar-pro' (web search with citations). "
                "Use gemini_list_models to see all available options."
            )
        },
        "provider": {
            "type": "string",
            "enum": ["auto", "gemini", "openrouter"],
            "description": (
                "Provider to use: 'auto' (default: Gemini IDs and aliases go to the Gemini API, "
                "falling back to OpenRouter's google/ mirror without a Gemini key; other IDs go to OpenRouter), "
                "'gemini' (Gemini API only), 'openrouter' (always OpenRouter: Gemini IDs become google/<id>, "
                "no model = OPENROUTER_DEFAULT_MODEL)"
            ),
            "default": "auto"
        },
        "system_prompt": {
            "type": "string",
            "description": "Optional system prompt / persona for the model"
        },
        "temperature": {
            "type": "number",
            "description": "Sampling temperature 0.0-1.0 (default: 0.7). Used by OpenRouter models, Gemini 2.x and Gemma; ignored by Gemini 3.6+ (deprecated upstream).",
            "default": 0.7,
            "minimum": 0.0,
            "maximum": 1.0
        }
    },
    "required": ["prompt"]
}

# All known Gemini model prefixes for auto-detection
_GEMINI_PREFIXES = (
    "gemini-", "models/gemini-", "gemma-", "models/gemma-", "imagen-", "veo-", "deep-research", "lyria-"
)

# Short aliases that always map to Gemini
_GEMINI_SHORT_NAMES = {"pro", "flash", "fast", "flash-lite"}

# Gemini model prefixes that have OpenRouter equivalents (text-only)
# veo-, imagen-, deep-research are Gemini-exclusive (no OpenRouter equivalent)
_OPENROUTER_FALLBACK_PREFIXES = ("gemini-", "models/gemini-", "gemma-", "models/gemma-")
_OPENROUTER_FALLBACK_SHORT_NAMES = {"pro", "flash", "fast", "flash-lite"}


def _is_gemini_model(model_id: str) -> bool:
    """Return True if model ID looks like a Gemini/Google model."""
    lower = model_id.lower()
    return lower in _GEMINI_SHORT_NAMES or any(lower.startswith(p) for p in _GEMINI_PREFIXES)


def _to_openrouter_google_id(model_id: str) -> Optional[str]:
    """Convert a Gemini native model ID to OpenRouter's google/ format.

    Returns None for models with no OpenRouter equivalent (veo, imagen, deep-research).
    OpenRouter mirrors Gemini text models as 'google/<model-id>'.
    """
    lower = model_id.lower()
    if lower in _OPENROUTER_FALLBACK_SHORT_NAMES:
        # Short names need resolution first — caller must resolve before calling this
        return None
    if lower.startswith(("models/gemini-", "models/gemma-")):
        return f"google/{model_id[7:]}"  # strip "models/" prefix
    if lower.startswith(("gemini-", "gemma-")):
        return f"google/{model_id}"
    return None  # veo-, imagen-, lyria-, deep-research → no OpenRouter equivalent


def _resolve_gemini_model(model_id: str) -> str:
    """Map short names like 'pro', 'flash' to full model IDs."""
    from ...services.model_registry import model_registry

    short_map = {
        "pro": "text_pro",
        "flash": "text_flash",
        "fast": "text_flash",
        "flash-lite": "text_flash_lite",
    }
    if model_id in short_map:
        return model_registry.resolve(short_map[model_id])
    return model_id


_PROVIDERS = ("auto", "gemini", "openrouter")
_NO_KEYS = (
    "Error: No API key configured.\n"
    "Set GEMINI_API_KEY for Gemini models, or "
    "OPENROUTER_API_KEY to access 400+ models (Google ones included) via OpenRouter."
)


def _via_gemini(
    prompt: str, model: Optional[str], system_prompt: Optional[str], temperature: float
) -> str:
    """Native Gemini API. Flash fallback on quota only when no exact ID was requested."""
    resolved = _resolve_gemini_model(model or "pro")
    explicit = model is not None and model.lower() not in _GEMINI_SHORT_NAMES
    try:
        # temperature is deprecated/ignored from Gemini 3.6 on: only 2.x and Gemma get it
        config_kwargs = legacy_sampling(resolved, temperature)
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        response = generate_with_fallback(
            model_id=resolved,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
            operation="ask_model",
            allow_fallback=not explicit,
        )
    except Exception as e:
        return f"Error: {e}"
    return response.text or f"Error: empty response from {resolved} (possibly blocked by safety filters)"


def _via_openrouter(
    prompt: str, model: Optional[str], system_prompt: Optional[str], temperature: float
) -> str:
    """OpenRouter. Gemini IDs/aliases map to google/<id>; no model = the OpenRouter default."""
    if not openrouter_client.is_available:
        target = f"model '{model}'" if model else "OpenRouter"
        return (
            f"Error: OPENROUTER_API_KEY required to use {target}.\n"
            "Set OPENROUTER_API_KEY to access 400+ models via OpenRouter."
        )
    or_model = model
    if model is not None and _is_gemini_model(model):
        resolved = _resolve_gemini_model(model)
        or_model = _to_openrouter_google_id(resolved)
        if or_model is None:
            return (
                f"Error: model '{resolved}' requires GEMINI_API_KEY "
                "(video/image/music/deep-research models are not available via OpenRouter)."
            )
    return openrouter_client.generate(
        prompt=prompt,
        model=or_model,
        system_prompt=system_prompt,
        temperature=temperature,
    )


@tool(
    name="ask_model",
    description=(
        "Ask any AI model — Gemini or 400+ models via OpenRouter "
        "(GPT, Claude, Llama, Mistral, Grok, DeepSeek, Perplexity…). "
        "provider='auto' detects from the model name; provider='openrouter' always uses OpenRouter. "
        "Requires OPENROUTER_API_KEY for non-Gemini models. "
        "Use gemini_list_models to discover available options."
    ),
    input_schema=ASK_MODEL_SCHEMA,
    tags=["text", "multi-provider", "openrouter"]
)
def ask_model(
    prompt: str,
    model: Optional[str] = None,
    provider: str = "auto",
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
) -> str:
    """
    Route prompt to Gemini or OpenRouter based on model/provider.

    Routing:
        provider='openrouter': always OpenRouter (Gemini IDs → google/<id>, no model → default)
        provider='gemini': Gemini API only (non-Gemini IDs are an error)
        provider='auto': Gemini IDs/aliases and no model → Gemini API, or OpenRouter
            without a Gemini key; any other ID → OpenRouter

    Args:
        prompt: The question or prompt
        model: Model ID or alias (auto-resolved if omitted)
        provider: 'auto', 'gemini', or 'openrouter'
        system_prompt: Optional system message
        temperature: Sampling temperature 0-1

    Returns:
        Model response text, or a message starting with "Error:"
    """
    model = (model or "").strip() or None
    provider = (provider or "auto").strip().lower()
    if provider not in _PROVIDERS:
        return f"Error: unknown provider '{provider}'. Use one of: {', '.join(_PROVIDERS)}."

    gemini_model = model is None or _is_gemini_model(model)

    if provider == "openrouter":
        return _via_openrouter(prompt, model, system_prompt, temperature)

    if provider == "gemini":
        if not gemini_model:
            return (
                f"Error: model '{model}' is not a Gemini model. "
                "Use provider='auto' or provider='openrouter' for non-Gemini models."
            )
        if not is_available():
            return f"Error: {get_error() or 'GEMINI_API_KEY is not configured'}"
        return _via_gemini(prompt, model, system_prompt, temperature)

    # provider == "auto"
    if not gemini_model:
        return _via_openrouter(prompt, model, system_prompt, temperature)
    if is_available():
        return _via_gemini(prompt, model, system_prompt, temperature)
    if openrouter_client.is_available:
        return _via_openrouter(prompt, model, system_prompt, temperature)
    return _NO_KEYS
