"""
Multi-Provider Ask Tool (v4.0.0)

Routes requests to Gemini or OpenRouter based on model ID / provider selection.
Enables access to 400+ models beyond Gemini.
"""

from typing import Optional

from ...tools.registry import tool
from ...services.model_registry import CATEGORY_PRIORITIES
from ...services.gemini import generate_with_fallback, types, is_available, get_error
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
                "Model ID to use. Gemini examples: 'gemini-3.1-pro-preview', 'gemini-2.5-flash'. "
                "OpenRouter examples: 'openai/gpt-4o', 'meta-llama/llama-3.3-70b', "
                "'anthropic/claude-3.5-sonnet'. "
                "Use gemini_list_models to see all available options."
            )
        },
        "provider": {
            "type": "string",
            "enum": ["auto", "gemini", "openrouter"],
            "description": (
                "Provider to use: 'auto' (detect from model name, default), "
                "'gemini' (force Gemini API), 'openrouter' (force OpenRouter)"
            ),
            "default": "auto"
        },
        "system_prompt": {
            "type": "string",
            "description": "Optional system prompt / persona for the model"
        },
        "temperature": {
            "type": "number",
            "description": "Sampling temperature 0.0-1.0 (default: 0.7)",
            "default": 0.7,
            "minimum": 0.0,
            "maximum": 1.0
        }
    },
    "required": ["prompt"]
}

# All known Gemini model prefixes for auto-detection
_GEMINI_PREFIXES = (
    "gemini-", "models/gemini-", "imagen-", "veo-", "deep-research"
)

# Short aliases that always map to Gemini
_GEMINI_SHORT_NAMES = {"pro", "flash", "fast", "flash-lite"}


def _is_gemini_model(model_id: str) -> bool:
    """Return True if model ID looks like a Gemini/Google model."""
    lower = model_id.lower()
    return lower in _GEMINI_SHORT_NAMES or any(lower.startswith(p) for p in _GEMINI_PREFIXES)


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


@tool(
    name="ask_model",
    description=(
        "Ask any AI model — Gemini or 400+ models via OpenRouter "
        "(GPT-4o, Llama 3, Mistral, Claude, etc.). "
        "Set provider='auto' to detect from model name. "
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

    Args:
        prompt: The question or prompt
        model: Model ID (auto-resolved if omitted)
        provider: 'auto', 'gemini', or 'openrouter'
        system_prompt: Optional system message
        temperature: Sampling temperature 0-1

    Returns:
        Model response text
    """
    from ...services.model_registry import model_registry

    # Determine effective provider
    if provider == "auto":
        if model is None or _is_gemini_model(model):
            effective_provider = "gemini"
        else:
            effective_provider = "openrouter"
    else:
        effective_provider = provider

    # --- Gemini path ---
    if effective_provider == "gemini":
        if not is_available():
            return f"Error: {get_error()}"

        resolved = _resolve_gemini_model(model or "pro")

        try:
            gen_config = types.GenerateContentConfig(temperature=temperature)
            if system_prompt:
                gen_config = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=system_prompt,
                )

            response = generate_with_fallback(
                model_id=resolved,
                contents=prompt,
                config=gen_config,
                operation="ask_model",
            )
            return response.text
        except Exception as e:
            return f"Error: {e}"

    # --- OpenRouter path ---
    if not openrouter_client.is_available:
        return (
            "Error: OpenRouter not configured.\n"
            "Set OPENROUTER_API_KEY to access 400+ models via OpenRouter."
        )

    return openrouter_client.generate(
        prompt=prompt,
        model=model or openrouter_client._default_model,
        system_prompt=system_prompt,
        temperature=temperature,
    )
