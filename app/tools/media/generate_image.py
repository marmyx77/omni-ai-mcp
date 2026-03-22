"""
Generate Image Tool

Image generation and editing using Gemini native image generation.
Supports text-to-image and image-to-image (editing/transformation).
"""

import base64
import os
from typing import Optional, List

from ...tools.registry import tool
from ...services import types, IMAGE_MODELS, client
from ...core import log_progress


GENERATE_IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "Detailed image description or transformation instruction. Be specific: describe scene, lighting, style, camera angle. For editing: describe the desired change (e.g. 'Add a sunset sky to this photo')."
        },
        "input_images": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional list of input image paths for editing or transformation. Provide one or more existing images to edit, combine, or use as reference. Supports PNG, JPG, JPEG, WEBP."
        },
        "model": {
            "type": "string",
            "enum": ["pro", "flash"],
            "description": "pro (default): Gemini 3 Pro - high quality, 4K, thinking mode. flash: Gemini 2.5 Flash - fast generation.",
            "default": "pro"
        },
        "aspect_ratio": {
            "type": "string",
            "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            "description": "Output aspect ratio.",
            "default": "1:1"
        },
        "image_size": {
            "type": "string",
            "enum": ["1K", "2K", "4K"],
            "description": "Resolution (only for pro model). 1K=1024px, 2K=2048px, 4K=4096px.",
            "default": "2K"
        },
        "output_path": {
            "type": "string",
            "description": "Path to save image (optional, returns base64 preview if not provided)."
        }
    },
    "required": ["prompt"]
}


def _load_image_part(image_path: str) -> types.Part:
    """Load an image file and return a Gemini Part."""
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime_type = mime_types.get(ext)
    if not mime_type:
        raise ValueError(f"Unsupported image format: {ext}. Supported: PNG, JPG, JPEG, WEBP")
    with open(image_path, "rb") as f:
        data = f.read()
    return types.Part.from_bytes(data=data, mime_type=mime_type)


@tool(
    name="gemini_generate_image",
    description=(
        "Generate or edit images using Gemini 3 Pro native image generation. "
        "This model has unique strengths over other image generators: "
        "(1) INFOGRAPHICS WITH ACCURATE DATA — Gemini grounds generation in real-world knowledge, "
        "so data labels, statistics, and facts inside the image are correct; "
        "(2) READABLE TEXT — renders legible text, labels, callouts, and annotations inside images "
        "(most diffusion models fail at this); "
        "(3) TECHNICAL DIAGRAMS — architecture diagrams, flowcharts, system schemas, "
        "process flows, network topologies; "
        "(4) CARTOGRAPHIC VISUALIZATIONS — maps, geographic distributions, spatial data; "
        "(5) DOCUMENT ILLUSTRATION — generate diagrams, timelines, and visual summaries "
        "to accompany technical or business documents. "
        "Use this tool proactively when a concept, process, or dataset would be clearer as a visual. "
        "For image editing or transformation, pass input_images with a transformation instruction "
        "(e.g. 'Add annotations to this diagram', 'Combine these two screenshots into a comparison')."
    ),
    input_schema=GENERATE_IMAGE_SCHEMA,
    tags=["media", "generation"]
)
def generate_image(
    prompt: str,
    input_images: Optional[List[str]] = None,
    model: str = "pro",
    aspect_ratio: str = "1:1",
    image_size: str = "2K",
    output_path: Optional[str] = None
) -> str:
    """
    Generate or edit images using Gemini native image generation.

    Models:
    - pro: gemini-3-pro-image-preview (high quality, up to 4K, thinking mode) - DEFAULT
    - flash: gemini-2.5-flash-image (fast, 1024px max)

    Modes:
    - Text-to-image: prompt only
    - Image editing: prompt + input_images (one or more images to edit/combine)
    """
    try:
        model_id = IMAGE_MODELS.get(model, IMAGE_MODELS["pro"])

        config_params = {
            "response_modalities": ["IMAGE", "TEXT"]
        }

        image_config = {"aspect_ratio": aspect_ratio}
        if model == "pro" and image_size in ["1K", "2K", "4K"]:
            image_config["image_size"] = image_size
        config_params["image_config"] = types.ImageConfig(**image_config)

        # Build contents: images first (if any), then prompt text
        if input_images:
            contents = []
            missing = [p for p in input_images if not os.path.exists(p)]
            if missing:
                return f"Error: Input image(s) not found: {', '.join(missing)}"
            for img_path in input_images:
                contents.append(_load_image_part(img_path))
            contents.append(prompt)
            mode = f"image editing ({len(input_images)} input image(s))"
        else:
            contents = prompt
            mode = "text-to-image"

        log_progress(f"Generating {image_size} image [{mode}] with {model_id}...")

        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=types.GenerateContentConfig(**config_params)
        )

        log_progress("Image generation completed")

        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                image_data = part.inline_data.data
                mime_type = part.inline_data.mime_type

                ext = ".png"
                if "jpeg" in mime_type:
                    ext = ".jpg"
                elif "webp" in mime_type:
                    ext = ".webp"

                if output_path:
                    if not output_path.endswith(ext):
                        output_path = output_path.rsplit('.', 1)[0] + ext
                    with open(output_path, 'wb') as f:
                        f.write(image_data)
                    return (
                        f"Image saved to: {output_path}\n"
                        f"Model: {model_id} | Mode: {mode}\n"
                        f"Aspect ratio: {aspect_ratio}"
                    )
                else:
                    b64 = base64.b64encode(image_data).decode('utf-8')
                    return (
                        f"Generated image ({mime_type})\n"
                        f"Model: {model_id} | Mode: {mode}\n"
                        f"Aspect ratio: {aspect_ratio}\n"
                        f"Base64 (first 100 chars): {b64[:100]}...\n"
                        f"Total size: {len(b64)} characters"
                    )

        text_parts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text') and p.text]
        if text_parts:
            return f"No image generated. Model response: {' '.join(text_parts)}"
        return "No image generated. Try a more descriptive prompt."

    except Exception as e:
        return f"Image generation error: {str(e)}"
