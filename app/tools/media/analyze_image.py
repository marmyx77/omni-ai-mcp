"""
Analyze Image Tool

Image analysis using Gemini vision capabilities.
Supports single or multiple images with configurable media resolution.
"""

import os
from typing import Optional, List

from ...tools.registry import tool
from ...services import types, MODELS, generate_with_fallback


MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

MEDIA_RESOLUTIONS = {
    "low": types.MediaResolution.MEDIA_RESOLUTION_LOW if hasattr(types, 'MediaResolution') else None,
    "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM if hasattr(types, 'MediaResolution') else None,
    "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH if hasattr(types, 'MediaResolution') else None,
}

ANALYZE_IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "image_path": {
            "type": "string",
            "description": "Local file path to the image. Use this for a single image. Supports PNG, JPG, JPEG, GIF, WEBP."
        },
        "image_paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of local image paths for multi-image analysis (e.g. compare screenshots, analyze a sequence). Overrides image_path if both are provided."
        },
        "prompt": {
            "type": "string",
            "description": "What to do with the image(s): 'describe', 'extract text', 'compare these images', or any specific question.",
            "default": "Describe this image in detail"
        },
        "model": {
            "type": "string",
            "enum": ["pro", "flash"],
            "description": "flash (default): Gemini 2.5 Flash - reliable vision. pro: Gemini 3 Pro - deeper reasoning.",
            "default": "flash"
        },
        "media_resolution": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Image resolution sent to the model. low: faster/cheaper. medium (default): balanced. high: best detail for complex images, diagrams, or dense text.",
            "default": "medium"
        }
    },
    "required": []
}


def _load_image_part(image_path: str) -> types.Part:
    """Load an image file and return a Gemini Part."""
    ext = os.path.splitext(image_path)[1].lower()
    mime_type = MIME_TYPES.get(ext)
    if not mime_type:
        raise ValueError(f"Unsupported image format: {ext}. Supported: PNG, JPG, JPEG, GIF, WEBP")
    with open(image_path, "rb") as f:
        data = f.read()
    return types.Part.from_bytes(data=data, mime_type=mime_type)


@tool(
    name="gemini_analyze_image",
    description=(
        "Analyze one or more images using Gemini vision. "
        "Use cases: describe images, extract text (OCR), identify objects, compare screenshots, "
        "review UI/UX, analyze diagrams, answer questions about images. "
        "Pass multiple images via image_paths to compare or analyze a sequence."
    ),
    input_schema=ANALYZE_IMAGE_SCHEMA,
    tags=["media", "vision"]
)
def analyze_image(
    image_path: Optional[str] = None,
    image_paths: Optional[List[str]] = None,
    prompt: str = "Describe this image in detail",
    model: str = "flash",
    media_resolution: str = "medium"
) -> str:
    """
    Analyze one or more images using Gemini vision.

    Supports: PNG, JPG, JPEG, GIF, WEBP
    Single image: pass image_path
    Multiple images: pass image_paths (for comparison, sequences, multi-screenshot analysis)
    """
    try:
        # Resolve image list
        paths: List[str] = []
        if image_paths:
            paths = image_paths
        elif image_path:
            paths = [image_path]
        else:
            return "Error: Provide image_path or image_paths."

        # Validate all paths exist
        missing = [p for p in paths if not os.path.exists(p)]
        if missing:
            return f"Error: Image(s) not found: {', '.join(missing)}"

        # Load image parts
        image_parts = []
        for p in paths:
            try:
                image_parts.append(_load_image_part(p))
            except ValueError as e:
                return f"Error: {e}"

        model_id = MODELS.get(model, MODELS["pro"])

        # Build config
        config_kwargs = {
            "temperature": 0.3,
            "max_output_tokens": 4096,
        }
        resolution_enum = MEDIA_RESOLUTIONS.get(media_resolution)
        if resolution_enum is not None:
            config_kwargs["media_resolution"] = resolution_enum

        response = generate_with_fallback(
            model_id=model_id,
            contents=[*image_parts, prompt],
            config=types.GenerateContentConfig(**config_kwargs),
            operation="analyze_image"
        )

        n = len(paths)
        label = f"{n} image{'s' if n > 1 else ''}"
        return f"[{label} analyzed with {model_id} @ {media_resolution} resolution]\n\n{response.text}"

    except Exception as e:
        return f"Image analysis error: {str(e)}"
