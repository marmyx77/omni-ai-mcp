"""
Model Discovery Tool (v4.0.0, auto-detect report since v4.6.0)

Exposes the dynamic model registry to the user, including OpenRouter if configured.
"""

from ...tools.registry import tool
from ...services.model_registry import model_registry, CATEGORY_SPECS
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

CATEGORY_LABELS = {
    "text_pro": "Text Pro",
    "text_flash": "Text Flash",
    "text_flash_lite": "Text Flash Lite",
    "image": "Image Generation (pro)",
    "image_flash": "Image Generation (flash)",
    "video": "Video Generation",
    "video_fast": "Video Generation (fast)",
    "video_lite": "Video Generation (lite)",
    "tts": "Text-to-Speech",
    "tts_pro": "Text-to-Speech (pro)",
    "deep_research": "Deep Research Agent",
}

SOURCE_LABELS = {
    "env": "env override",
    "auto": "auto-detected",
    "fallback": "static fallback",
    "config": "config default",
}

_MAX_RUNNERS_UP = 3


def _format_category(category: str) -> str:
    """One report line: label, resolved model, provenance, runners-up."""
    label = CATEGORY_LABELS.get(category, category)
    res = model_registry.explain(category)
    source = SOURCE_LABELS.get(res.source, res.source)
    line = f"- **{label}**: `{res.model}` ({source}"
    if res.source == "env":
        line += f", `{CATEGORY_SPECS[category].env_var}`"
    line += ")"
    runners_up = [c for c in res.candidates if c != res.model][:_MAX_RUNNERS_UP]
    if runners_up:
        line += " — also: " + ", ".join(f"`{c}`" for c in runners_up)
    return line


def _gemini_section() -> list:
    lines = ["**Gemini Models (by category):**\n"]
    if model_registry.discovery_succeeded:
        count = len(model_registry.available_models)
        mode = "on" if model_registry.autodetect_enabled() else "off (GEMINI_MODEL_AUTODETECT=false)"
        lines.append(f"*Discovered {count} models via API — auto-detect {mode}.*\n")
    else:
        lines.append("*API discovery unavailable — showing static fallbacks.*\n")

    lines.extend(_format_category(category) for category in CATEGORY_SPECS)

    deprecated = model_registry.check_deprecated()
    if deprecated:
        lines.append("\n**Config defaults no longer exposed by the API:**")
        lines.extend(f"- {d}" for d in deprecated)
        lines.append("*Harmless while auto-detect is on; update the GEMINI_MODEL_* default otherwise.*")
    return lines


def _openrouter_section() -> list:
    lines = ["\n**OpenRouter (400+ models):**"]
    if not openrouter_client.is_available:
        lines.append("- Not configured (set OPENROUTER_API_KEY to enable)")
        return lines
    model_ids = openrouter_client.list_model_ids()
    if not model_ids:
        lines.append("- API key set but could not fetch model list")
        return lines
    lines.append(f"- Available: {len(model_ids)} models")
    lines.append("- Popular: " + ", ".join(f"`{m}`" for m in model_ids[:5]))
    lines.append("*Use `ask_model` to query any of these models.*")
    return lines


@tool(
    name="gemini_list_models",
    description="List available AI models by category. Shows the Gemini model auto-detected per category (newest the API exposes), where each choice came from (auto-detect, env override, fallback), and OpenRouter models if configured.",
    input_schema=LIST_MODELS_SCHEMA,
    tags=["models", "discovery"]
)
def list_models(include_openrouter: bool = True) -> str:
    """
    List models from the Gemini API (auto-detected per category) and optionally OpenRouter.

    Returns:
        Formatted report of resolved models per category with provenance
    """
    lines = ["**Available AI Models**\n"]
    lines.extend(_gemini_section())
    if include_openrouter:
        lines.extend(_openrouter_section())
    return "\n".join(lines)
