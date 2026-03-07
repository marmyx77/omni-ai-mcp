"""
File Search Tool

Query documents using RAG with File Search Stores.
"""

from ...tools.registry import tool
from ...services import types, generate_with_fallback, MODELS
from .file_store import resolve_store_name


FILE_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "Question to ask about the documents"},
        "store_name": {"type": "string", "description": "File Search Store name (display name or full path)"}
    },
    "required": ["question", "store_name"]
}


@tool(
    name="gemini_file_search",
    description="Query documents in a File Search Store using RAG",
    input_schema=FILE_SEARCH_SCHEMA,
    tags=["rag", "search"]
)
def file_search(question: str, store_name: str) -> str:
    """Query documents using File Search RAG."""
    # Resolve short name to full path
    try:
        resolved_store = resolve_store_name(store_name)
    except ValueError as e:
        return f"Error: {e}"

    response = generate_with_fallback(
        model_id=MODELS["flash"],
        contents=question,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[resolved_store]
                    )
                )
            ]
        ),
        operation="file_search"
    )

    result = response.text

    # Add citations if available
    if hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
            metadata = candidate.grounding_metadata
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                result += "\n\n**Citations:**\n"
                for i, chunk in enumerate(metadata.grounding_chunks[:5], 1):
                    if hasattr(chunk, 'retrieved_context'):
                        ctx = chunk.retrieved_context
                        result += f"{i}. {ctx.title if hasattr(ctx, 'title') else 'Document'}\n"

    return result
