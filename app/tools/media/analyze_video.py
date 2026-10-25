"""
Analyze Video Tool (v4.8.0)

Video understanding on a local file or a public YouTube URL: summaries,
Q&A, timestamps (MM:SS), transcripts of what is said and shown.

- processing="static" (default): frames at 1 FPS in one pass — best for short
  clips (< ~5 min) and whole-video summaries.
- processing="agentic": the model navigates the timeline on demand (transcript
  first, then only the relevant segments) — up to 88% fewer tokens and better
  quality on long videos and needle-in-a-haystack questions. Supported on
  Gemini 4 Argon, 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite.
- model="robotics": Gemini Robotics ER for spatial/temporal reasoning (point to
  or track objects across frames, progress of a task) in JSON.
"""

import re
from typing import List, Optional

from ...tools.registry import tool
from ...services import MODELS, is_available, get_error
from ...services import interactions as ix
from ...core import config

PROCESSING = ("static", "agentic")
RESOLUTIONS = ("low", "medium", "high")
YOUTUBE_RE = re.compile(r"^https?://(www\.|m\.)?(youtube\.com/(watch|shorts|live)|youtu\.be/)", re.I)
AGENTIC_FAMILIES = re.compile(r"^gemini-(4[.-]|3\.8-flash|3\.6-flash|3\.5-flash-lite)")
POLL_SECONDS = 5

ANALYZE_VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "description": "What to do: summarize, answer a question, list key moments with MM:SS timestamps, transcribe..."},
        "video_path": {"type": "string", "description": "Local video file (mp4, mov, webm, ...). Uploaded through the Files API."},
        "youtube_url": {"type": "string", "description": "Public YouTube URL (alternative to video_path)."},
        "processing": {
            "type": "string", "enum": list(PROCESSING), "default": "static",
            "description": "static (default): 1 FPS, best for short clips/full summaries. agentic: on-demand timeline navigation, best for long videos and specific moments (4 Argon, 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite)."
        },
        "model": {
            "type": "string", "enum": ["flash", "pro", "flash-lite", "robotics"], "default": "flash",
            "description": "flash (default), pro (newest flagship), flash-lite (cheapest), robotics (spatial/temporal reasoning in JSON)."
        },
        "resolution": {"type": "string", "enum": list(RESOLUTIONS), "description": "Optional frame resolution (higher = more detail, more tokens)."},
        "max_wait_minutes": {"type": "integer", "minimum": 1, "maximum": 60, "default": 20}
    },
    "required": ["prompt"]
}


def build_video_analysis_request(model_id: str, video_block: dict, prompt: str) -> dict:
    return {
        "model": model_id,
        "input": [video_block, {"type": "text", "text": prompt}],
        "generation_config": {"max_output_tokens": config.max_output_tokens},
        "background": True,
    }


def video_block_for(video_path: Optional[str], youtube_url: Optional[str],
                    processing: str, resolution: Optional[str]):
    """Content block for the video plus the Files API name to delete afterwards."""
    if bool(video_path) == bool(youtube_url):
        raise ValueError("provide exactly one of video_path or youtube_url")
    if processing not in PROCESSING:
        raise ValueError(f"processing must be one of {PROCESSING}")
    if resolution and resolution not in RESOLUTIONS:
        raise ValueError(f"resolution must be one of {RESOLUTIONS}")
    extra = {}
    if processing == "agentic":
        extra["processing"] = "agentic"
    if resolution:
        extra["resolution"] = resolution
    if youtube_url:
        if not YOUTUBE_RE.match(youtube_url):
            raise ValueError("youtube_url must be a public youtube.com or youtu.be link")
        return {"type": "video", "uri": youtube_url, **extra}, None
    if ix.kind_for(ix.mime_for(video_path)) != "video":
        raise ValueError(f"{video_path} is not a video file")
    return ix.file_block(video_path, force_upload=True, **extra)


@tool(
    name="gemini_analyze_video",
    description=(
        "Understand a video (local file or public YouTube URL): summaries, Q&A, key moments with MM:SS timestamps, "
        "what is said and shown. processing='agentic' navigates long videos on demand (up to 88% fewer tokens); "
        "model='robotics' answers spatial/temporal questions in JSON."
    ),
    input_schema=ANALYZE_VIDEO_SCHEMA,
    tags=["media", "video", "vision"]
)
def analyze_video(
    prompt: str,
    video_path: Optional[str] = None,
    youtube_url: Optional[str] = None,
    processing: str = "static",
    model: str = "flash",
    resolution: Optional[str] = None,
    max_wait_minutes: int = 20,
) -> str:
    """Analyze a video with Gemini (static or agentic processing)."""
    if not is_available():
        return f"Error: {get_error()}"
    uploaded: List[Optional[str]] = []
    try:
        model_id = MODELS[model] if model in MODELS else MODELS["flash"]
        if processing == "agentic" and not AGENTIC_FAMILIES.match(model_id):
            return (f"Error: agentic processing is not supported by {model_id}. "
                    "Use model='flash', 'pro' or 'flash-lite', or processing='static'.")
        block, name = video_block_for(video_path, youtube_url, processing, resolution)
        uploaded.append(name)
        interaction = ix.run(build_video_analysis_request(model_id, block, prompt),
                             max(1, int(max_wait_minutes)) * 60, POLL_SECONDS)
        text = ix.output_text(interaction)
        if not text:
            return f"No analysis returned (interaction {ix._get(interaction, 'id')})."
        footer = f"*{model_id} · {processing} processing"
        usage = ix.usage_line(interaction)
        if usage:
            footer += f" · {usage}"
        return f"{text}\n\n---\n{footer}*"
    except FileNotFoundError as e:
        return f"Error: file not found: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except ix.InteractionTimeout as t:
        return (f"Analysis still running after {t.waited_seconds // 60} min (interaction {t.interaction_id}). "
                "Retry with a higher max_wait_minutes, or use processing='agentic' for long videos.")
    except Exception as e:
        return f"Video analysis error: {e}"
    finally:
        ix.cleanup(uploaded)
