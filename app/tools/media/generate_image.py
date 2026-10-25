"""
Generate Image Tool (Nano Banana family, v4.8.0)

- pro: Nano Banana Pro (newest Gemini Pro Image): highest quality, 4K, thinking
- flash: Nano Banana 2.1 (newest Gemini Flash Image): Flash-speed, 1K/2K/4K,
  panoramic 1:4, 4:1, 1:8, 8:1, up to 14 reference images, Google Search grounding
- lite: Nano Banana 2 Lite: lowest latency and cost

Supports text-to-image and image-to-image (editing, fusion, references).
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
            "description": "Optional input images (up to 14) to edit, combine or use as references (character consistency up to 4 people, object fidelity up to 10 objects on flash). PNG, JPG, JPEG, WEBP."
        },
        "model": {
            "type": "string",
            "enum": ["pro", "flash", "lite"],
            "description": "pro (default): Nano Banana Pro, highest quality. flash: Nano Banana 2.1, fast, panoramic formats, 14 references. lite: Nano Banana 2 Lite, cheapest and fastest. Exact IDs auto-detected.",
            "default": "pro"
        },
        "aspect_ratio": {
            "type": "string",
            "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "1:4", "4:1", "1:8", "8:1"],
            "description": "Output aspect ratio. Panoramic 1:4, 4:1, 1:8, 8:1 are for model='flash' (Nano Banana 2.1).",
            "default": "1:1"
        },
        "image_size": {
            "type": "string",
            "enum": ["auto", "512", "1K", "2K", "4K"],
            "description": "Resolution. auto (default): 2K on pro, the model default (1K) on flash/lite. 4K costs more.",
            "default": "auto"
        },
        "google_search": {
            "type": "boolean",
            "description": "Ground the image in Google Search results (facts, current events, real places) for accurate infographics.",
            "default": False
        },
        "thinking_level": {
            "type": "string",
            "enum": ["auto", "minimal", "medium", "high"],
            "description": "Reasoning before drawing (flash: minimal/medium default/high). auto lets the model decide.",
            "default": "auto"
        },
        "output_path": {
            "type": "string",
            "description": "Path to save image (optional, returns base64 preview if not provided)."
        }
    },
    "required": ["prompt"]
}


MAX_REFERENCE_IMAGES = 14


def resolve_image_size(model: str, image_size: str) -> Optional[str]:
    """auto → 2K on pro (previous default), model default elsewhere; explicit sizes pass through."""
    if image_size in ("512", "1K", "2K", "4K"):
        return image_size
    return "2K" if model == "pro" else None


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
        "Generate or edit images with Google's Nano Banana models (Pro, 2.1, 2 Lite). "
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
    image_size: str = "auto",
    output_path: Optional[str] = None,
    google_search: bool = False,
    thinking_level: str = "auto",
) -> str:
    """
    Generate or edit images using Gemini native image generation.

    Models:
    - pro: Nano Banana Pro (newest Gemini Pro Image) - DEFAULT
    - flash: Nano Banana 2.1 (fast, panoramic formats, 14 references, search grounding)
    - lite: Nano Banana 2 Lite (lowest latency and cost)

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
        size = resolve_image_size(model, image_size)
        if size:
            image_config["image_size"] = size
        config_params["image_config"] = types.ImageConfig(**image_config)
        if google_search:
            config_params["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        if thinking_level and thinking_level != "auto":
            config_params["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level)

        # Build contents: images first (if any), then prompt text
        if input_images and len(input_images) > MAX_REFERENCE_IMAGES:
            return f"Error: at most {MAX_REFERENCE_IMAGES} input images"
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

        log_progress(f"Generating {size or 'default-size'} image [{mode}] with {model_id}...")

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
