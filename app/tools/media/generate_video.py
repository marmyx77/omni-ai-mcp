"""
Generate Video Tool (Gemini Omni Flash, v4.8.0)

Veo 3.1 Preview was shut down in the Gemini API on 2026-10-22. Video now runs on
Gemini Omni Flash (newest gemini-omni-*-flash, via the Interactions API):

- text to video, image to video, subject/style references (<IMAGE_REF_N> tags),
  first+last frame interpolation (<FIRST_FRAME> <LAST_FRAME> tags)
- conversational editing and extension of a generated video (continuation_id)
- editing/extending an uploaded clip (≤ 10 s; not available in the EEA, CH, UK)
- 3–10 s clips with native audio, 16:9 or 9:16, 360p/720p (native), 1080p/4k (upscaled)
"""

import os
from typing import List, Optional

from ...tools.registry import tool
from ...services import VIDEO_MODELS, is_available, get_error
from ...services import interactions as ix

TASKS = ("auto", "text_to_video", "image_to_video", "reference_to_video", "edit", "extend")
ASPECT_RATIOS = ("16:9", "9:16")
RESOLUTIONS = ("360p", "720p", "1080p", "4k")
URI_DELIVERY = ("1080p", "4k")          # docs: use delivery="uri" above ~4 MB
LEGACY_MODELS = ("veo31", "veo31_fast", "veo31_lite", "veo3", "veo3_fast", "veo2")
MAX_IMAGES = 14
POLL_SECONDS = 10

GENERATE_VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": (
                "What to generate or change. Describe subject, action, camera, lighting, audio. "
                "Timing works in natural language or timecodes ('[0-3s] ... [3-6s] ...'). "
                "Bind images with tags: <FIRST_FRAME>, <LAST_FRAME>, <IMAGE_REF_0>... For edits, keep prompts short "
                "and add 'Keep everything else the same'."
            )
        },
        "image_paths": {
            "type": "array", "items": {"type": "string"},
            "description": "Optional local images: a starting frame, first+last frames for interpolation, or subject/style references (up to 14)."
        },
        "video_path": {
            "type": "string",
            "description": "Optional local clip (≤ 10 s) to edit or extend. Not available in the EEA, Switzerland and the UK (editing/extending generated videos via continuation_id is)."
        },
        "task": {
            "type": "string", "enum": list(TASKS), "default": "auto",
            "description": "auto (default): the model infers it from prompt and inputs. Set it only if the model misreads the intent."
        },
        "aspect_ratio": {"type": "string", "enum": list(ASPECT_RATIOS), "default": "16:9"},
        "resolution": {
            "type": "string", "enum": list(RESOLUTIONS), "default": "720p",
            "description": "360p/720p native; 1080p and 4k are upscaled and delivered by URI."
        },
        "duration": {
            "type": "integer", "minimum": 3, "maximum": 10,
            "description": "Optional clip length in seconds (3-10). Omit to let the model decide."
        },
        "negative_prompt": {
            "type": "string",
            "description": "What to avoid. Omni has no negative-prompt field: it is appended to the prompt as an 'Avoid:' line."
        },
        "continuation_id": {
            "type": "string",
            "description": "interaction_id of a previously generated video: the prompt edits or extends THAT video (stateful, no re-upload)."
        },
        "retrieve_id": {
            "type": "string",
            "description": "interaction_id of a generation that timed out: fetch and save its video (waits if still running). Other inputs are ignored."
        },
        "output_path": {"type": "string", "description": "Where to save the .mp4 (default /tmp)."},
        "max_wait_minutes": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10}
    },
    "required": ["prompt"]
}


def build_video_request(
    model_id: str,
    prompt: str,
    image_blocks: List[dict],
    video_block: Optional[dict],
    task: str,
    aspect_ratio: str,
    resolution: str,
    duration: Optional[int],
    negative_prompt: Optional[str],
    continuation_id: Optional[str],
) -> dict:
    """Interactions create() kwargs for Omni Flash (validated in tests against the SDK schema)."""
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError(f"aspect_ratio must be one of {ASPECT_RATIOS} (Omni supports landscape and portrait only)")
    if resolution not in RESOLUTIONS:
        raise ValueError(f"resolution must be one of {RESOLUTIONS}")
    if duration is not None and not 3 <= int(duration) <= 10:
        raise ValueError("duration must be between 3 and 10 seconds")
    if len(image_blocks) > MAX_IMAGES:
        raise ValueError(f"at most {MAX_IMAGES} images")

    text = prompt.strip()
    if negative_prompt:
        text += f"\nAvoid: {negative_prompt.strip()}"
    blocks = ([video_block] if video_block else []) + list(image_blocks)
    request = {
        "model": model_id,
        "input": blocks + [{"type": "text", "text": text}] if blocks else text,
        "response_format": {
            "type": "video",
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "delivery": "uri" if resolution in URI_DELIVERY else "inline",
        },
        "background": True,
    }
    if duration is not None:
        request["response_format"]["duration"] = f"{int(duration)}s"
    if task != "auto":
        request["generation_config"] = {"video_config": {"task": task}}
    if continuation_id:
        request["previous_interaction_id"] = continuation_id
    return request


def _result(interaction, output_path: Optional[str], note: str = "") -> str:
    item = ix.output_media(interaction, "video")
    interaction_id = ix._get(interaction, "id")
    if item is None:
        text = ix.output_text(interaction)
        return f"No video returned (interaction {interaction_id}). Model said: {text or 'nothing'}"
    path, size = ix.save_media(item, output_path, "gemini_video")
    lines = [
        "Video generated successfully!",
        f"- Saved to: {path} ({size // 1024} KB)",
        f"- Model: {ix._get(interaction, 'model') or VIDEO_MODELS['omni']}",
        f"- continuation_id: {interaction_id}  (pass it back to edit or extend this video)",
    ]
    usage = ix.usage_line(interaction)
    if usage:
        lines.append(f"- Usage: {usage}")
    if note:
        lines.append(f"- Note: {note}")
    return "\n".join(lines)


@tool(
    name="gemini_generate_video",
    description=(
        "Generate or edit a 3-10 s video with native audio using Gemini Omni Flash: text to video, image to video, "
        "subject/style references, first+last frame interpolation, conversational edits and extensions of a generated "
        "video (continuation_id), edits/extensions of an uploaded clip ≤ 10 s. 16:9 or 9:16, up to 4K (upscaled)."
    ),
    input_schema=GENERATE_VIDEO_SCHEMA,
    tags=["media", "video"]
)
def generate_video(
    prompt: str,
    image_paths: Optional[List[str]] = None,
    video_path: Optional[str] = None,
    task: str = "auto",
    aspect_ratio: str = "16:9",
    resolution: str = "720p",
    duration: Optional[int] = None,
    negative_prompt: Optional[str] = None,
    continuation_id: Optional[str] = None,
    retrieve_id: Optional[str] = None,
    output_path: Optional[str] = None,
    max_wait_minutes: int = 10,
    model: str = "omni",
) -> str:
    """Generate, edit or extend a video with Gemini Omni Flash (Interactions API)."""
    if not is_available():
        return f"Error: {get_error()}"
    timeout = max(1, int(max_wait_minutes)) * 60
    note = ""
    if model in LEGACY_MODELS:
        note = f"model '{model}' (Veo) was shut down upstream on 2026-10-22; used Gemini Omni Flash instead"

    if retrieve_id:
        try:
            return _result(ix.wait(retrieve_id, timeout, POLL_SECONDS), output_path, note)
        except ix.InteractionTimeout as t:
            return _timeout_message(t)
        except Exception as e:
            return f"Video retrieval error: {e}"

    uploaded: List[Optional[str]] = []
    try:
        video_block = None
        if video_path:
            if ix.kind_for(ix.mime_for(video_path)) != "video":
                return f"Error: {video_path} is not a video file"
            video_block, name = ix.file_block(video_path, force_upload=True)
            uploaded.append(name)
        image_blocks = []
        for img in image_paths or []:
            if ix.kind_for(ix.mime_for(img)) != "image":
                return f"Error: {img} is not an image file"
            block, name = ix.file_block(img)
            image_blocks.append(block)
            uploaded.append(name)

        request = build_video_request(
            VIDEO_MODELS["omni"], prompt, image_blocks, video_block, task,
            aspect_ratio, resolution, duration, negative_prompt, continuation_id,
        )
        interaction = ix.run(request, timeout, POLL_SECONDS)
        return _result(interaction, output_path, note)

    except FileNotFoundError as e:
        return f"Error: file not found: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except ix.InteractionTimeout as t:
        return _timeout_message(t)
    except Exception as e:
        return f"Video generation error: {e}"
    finally:
        ix.cleanup(uploaded)


def _timeout_message(t: "ix.InteractionTimeout") -> str:
    return (
        f"Video still generating after {t.waited_seconds // 60} min (it keeps running on Google's side).\n"
        f"Call gemini_generate_video again with retrieve_id='{t.interaction_id}' to save it when ready."
    )
