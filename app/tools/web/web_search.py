"""
Web Search Tool

Search the web using Gemini with Google Search grounding.
"""

from ...tools.registry import tool
from ...services import types, MODELS, generate_with_fallback


WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"},
        "model": {
            "type": "string",
            "enum": ["pro", "flash"],
            "description": "pro: Gemini 3 Pro - better synthesis. flash (default): faster for simple queries",
            "default": "flash"
        }
    },
    "required": ["query"]
}


@tool(
    name="gemini_web_search",
    description="Search the web using Gemini with Google Search grounding. Returns answers with citations.",
    input_schema=WEB_SEARCH_SCHEMA,
    tags=["web", "search"]
)
def web_search(query: str, model: str = "flash") -> str:
    """Web search with Google grounding."""
    model_id = MODELS.get(model, MODELS["flash"])

    response = generate_with_fallback(
        model_id=model_id,
        contents=query,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
        operation="web_search"
    )

    result = response.text

    # Extract grounding metadata if available
    if hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
            metadata = candidate.grounding_metadata
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                result += "\n\n**Sources:**\n"
                for chunk in metadata.grounding_chunks[:5]:
                    if hasattr(chunk, 'web') and chunk.web:
                        result += f"- [{chunk.web.title}]({chunk.web.uri})\n"

    return result
