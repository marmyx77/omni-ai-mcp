"""
Model Discovery Tool (v4.0.0)

Exposes the dynamic model registry to the user, including OpenRouter if configured.
"""

import json
from ...tools.registry import tool
from ...services.model_registry import model_registry
from ...services.openrouter import openrouter_client


LIST_MODELS_SCHEMA = {
    "type": "object",
    "properties": {
        "include_openrouter": {
            "type": "boolean",
            "description": "Include OpenRouter models in results (requires OPENROUTER_API_KEY). Default: true",
            "default": True
        }
    }
}


@tool(
    name="gemini_list_models",
    description="List available AI models by category. Shows Gemini models discovered via API and OpenRouter models if configured. Identifies deprecated models in your config.",
    input_schema=LIST_MODELS_SCHEMA,
    tags=["models", "discovery"]
)
def list_models(include_openrouter: bool = True) -> str:
    """
    List available models from Gemini API and optionally OpenRouter.

    Returns:
        Formatted report of available models per category
    """
    gemini_info = model_registry.list_available()

    lines = ["**Available AI Models**\n"]
    lines.append("**Gemini Models (by category):**\n")

    category_labels = {
        "text_pro": "Text Pro",
        "text_flash": "Text Flash",
        "text_flash_lite": "Text Flash Lite",
        "image": "Image Generation",
        "video": "Video Generation",
        "tts": "Text-to-Speech",
        "deep_research": "Deep Research Agent",
    }

    for category, label in category_labels.items():
        model = gemini_info.get(category, "unknown")
        lines.append(f"- **{label}**: `{model}`")

    deprecated = gemini_info.get("deprecated_in_config", [])
    if deprecated:
        lines.append(f"\n**Deprecated models still in config:**")
        for d in deprecated:
            lines.append(f"- {d}")
        lines.append("*Update via environment variables (e.g. GEMINI_MODEL_PRO)*")

    # OpenRouter section
    if include_openrouter:
        lines.append("\n**OpenRouter (400+ models):**")
        if not openrouter_client.is_available:
            lines.append("- Not configured (set OPENROUTER_API_KEY to enable)")
        else:
            model_ids = openrouter_client.list_model_ids()
            if model_ids:
                lines.append(f"- Available: {len(model_ids)} models")
                lines.append("- Popular: " + ", ".join(
                    f"`{m}`" for m in model_ids[:5]
                ))
                lines.append("*Use `ask_model` to query any of these models.*")
            else:
                lines.append("- API key set but could not fetch model list")

    return "\n".join(lines)
