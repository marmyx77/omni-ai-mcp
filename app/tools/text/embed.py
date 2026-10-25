"""
Embeddings Tool (Gemini Embedding 2, multimodal, v4.8.0)

Maps text, images (PNG/JPEG, ≤ 6), audio (MP3/WAV, ≤ 180 s), video and PDF into
one embedding space for semantic search, clustering, classification and
cross-modal retrieval. 3072 dims by default; 768/1536 recommended for storage
(Matryoshka, auto-renormalized). Total input ≤ 8192 tokens per request.

Gemini Embedding 2 has no task_type: the task goes in the text as a prefix
("task: search result | query: ..."); this tool adds it for you. Multiple
inputs are embedded SEPARATELY by default; aggregate=True returns one vector for
all of them (e.g. a post with text + images).
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from ...tools.registry import tool
from ...services import client, types, is_available, get_error
from ...services.model_registry import model_registry
from ...services import interactions as ix

QUERY_TASKS = {
    "search_query": "search result",
    "question_answering": "question answering",
    "fact_checking": "fact checking",
    "code_retrieval": "code retrieval",
    "classification": "classification",
    "clustering": "clustering",
    "similarity": "sentence similarity",
}
TASKS = ("none", "search_document") + tuple(QUERY_TASKS)
# gemini-embedding-001 still uses task_type instead of prefixes
LEGACY_TASK_TYPES = {
    "search_query": "RETRIEVAL_QUERY", "search_document": "RETRIEVAL_DOCUMENT",
    "question_answering": "QUESTION_ANSWERING", "fact_checking": "FACT_VERIFICATION",
    "code_retrieval": "CODE_RETRIEVAL_QUERY", "classification": "CLASSIFICATION",
    "clustering": "CLUSTERING", "similarity": "SEMANTIC_SIMILARITY",
}
DIMENSIONS = (128, 256, 512, 768, 1536, 2048, 3072)
INLINE_VALUE_LIMIT = 4096        # above this many floats, write to a file instead of returning them
MAX_IMAGES = 6

EMBED_SCHEMA = {
    "type": "object",
    "properties": {
        "texts": {"type": "array", "items": {"type": "string"}, "description": "Texts to embed (one vector each unless aggregate=true)."},
        "file_paths": {"type": "array", "items": {"type": "string"}, "description": "Images (PNG/JPEG, ≤ 6), audio (MP3/WAV ≤ 180 s), video, PDF."},
        "task": {
            "type": "string", "enum": list(TASKS), "default": "none",
            "description": "Adds Google's recommended prefix: search_query vs search_document for retrieval; similarity, clustering, classification, question_answering, fact_checking, code_retrieval."
        },
        "title": {"type": "string", "description": "Title for search_document texts (default 'none')."},
        "aggregate": {"type": "boolean", "default": False, "description": "One vector for all inputs together instead of one per input."},
        "output_dimensionality": {"type": "integer", "enum": list(DIMENSIONS), "description": "Vector size (default 3072; 768 or 1536 recommended to save space)."},
        "output_path": {"type": "string", "description": "Save the vectors as JSON here (recommended for many or large vectors)."}
    }
}


def prepare_text(text: str, task: str, title: Optional[str] = None) -> str:
    """Apply the Gemini Embedding 2 task prefix."""
    if task == "search_document":
        return f"title: {title or 'none'} | text: {text}"
    if task in QUERY_TASKS:
        return f"task: {QUERY_TASKS[task]} | query: {text}"
    return text


def build_embed_call(model_id: str, texts: List[str], file_parts: List[Any], task: str,
                     title: Optional[str], aggregate: bool, dims: Optional[int]) -> Dict[str, Any]:
    """Arguments for client.models.embed_content."""
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    if dims is not None and dims not in DIMENSIONS:
        raise ValueError(f"output_dimensionality must be one of {DIMENSIONS}")
    if not texts and not file_parts:
        raise ValueError("provide texts and/or file_paths")
    legacy = model_id.startswith("gemini-embedding-0")
    if legacy and file_parts:
        raise ValueError(f"{model_id} is text-only: use gemini-embedding-2 for images, audio, video, PDF")
    text_parts = [types.Part(text=t if legacy else prepare_text(t, task, title)) for t in texts]
    parts = text_parts + list(file_parts)
    contents = parts if aggregate else [types.Content(parts=[p]) for p in parts]
    cfg: Dict[str, Any] = {}
    if dims:
        cfg["output_dimensionality"] = dims
    if legacy and task in LEGACY_TASK_TYPES:
        cfg["task_type"] = LEGACY_TASK_TYPES[task]
    return {"model": model_id, "contents": contents, "config": types.EmbedContentConfig(**cfg) if cfg else None}


def _label(texts: List[str], files: List[str], aggregate: bool) -> List[str]:
    labels = [t[:60] for t in texts] + [os.path.basename(f) for f in files]
    return ["+".join(labels)] if aggregate else labels


@tool(
    name="gemini_embed",
    description=(
        "Create embeddings with Gemini Embedding 2 (multimodal): text, images, audio, video and PDF in one vector space "
        "for semantic search, clustering, classification and cross-modal retrieval. Adds the task prefix for you; "
        "one vector per input or one aggregated vector. Saves JSON for large outputs."
    ),
    input_schema=EMBED_SCHEMA,
    tags=["text", "embeddings", "rag"]
)
def embed(
    texts: Optional[List[str]] = None,
    file_paths: Optional[List[str]] = None,
    task: str = "none",
    title: Optional[str] = None,
    aggregate: bool = False,
    output_dimensionality: Optional[int] = None,
    output_path: Optional[str] = None,
) -> str:
    """Embed texts and files with the newest Gemini embedding model."""
    if not is_available():
        return f"Error: {get_error()}"
    texts = [t for t in (texts or []) if t and t.strip()]
    files = list(file_paths or [])
    try:
        file_parts = []
        images = 0
        for path in files:
            mime = ix.mime_for(path)
            images += mime.startswith("image/")
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            with open(path, "rb") as fh:
                file_parts.append(types.Part.from_bytes(data=fh.read(), mime_type=mime))
        if images > MAX_IMAGES:
            raise ValueError(f"at most {MAX_IMAGES} images per request")

        model_id = model_registry.resolve("embedding")
        result = client.models.embed_content(
            **build_embed_call(model_id, texts, file_parts, task, title, aggregate, output_dimensionality)
        )
        vectors = [list(e.values or []) for e in (result.embeddings or [])]
        if not vectors:
            return "No embeddings returned."
        labels = _label(texts, files, aggregate)
        payload = {
            "model": model_id, "task": task, "dimensions": len(vectors[0]),
            "items": [{"input": labels[i] if i < len(labels) else f"#{i}", "values": v} for i, v in enumerate(vectors)],
        }
        total = sum(len(v) for v in vectors)
        if output_path or total > INLINE_VALUE_LIMIT:
            path = output_path or f"/tmp/gemini_embeddings_{int(time.time())}.json"
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            return (f"{len(vectors)} embedding(s) × {payload['dimensions']} dims with {model_id}\n"
                    f"- Saved to: {path}\n- Inputs: {', '.join(i['input'] for i in payload['items'])}")
        return json.dumps(payload)
    except FileNotFoundError as e:
        return f"Error: file not found: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Embedding error: {e}"
