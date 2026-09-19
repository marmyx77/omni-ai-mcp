"""
Generate Video Tool

Video generation using Google Veo 3.1 with native audio.

v3.0.2: Removed async polling that caused deadlocks in FastMCP.
"""

import time
from typing import Optional

from ...tools.registry import tool
from ...services import types, VIDEO_MODELS, client
from ...core import log_progress


GENERATE_VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "Detailed video description. Include: subject, action, style, camera motion, ambiance. For dialogue use quotes: 'Hello,' she said. For sounds describe explicitly: engine roaring, birds chirping."
        },
        "model": {
            "type": "string",
            "enum": ["veo31", "veo31_fast", "veo31_lite"],
            "description": "veo31 (default): Best quality with native audio. veo31_fast: Faster. veo31_lite: Cheapest, 720p only. The exact model ID is auto-detected (newest Veo the API exposes).",
            "default": "veo31"
        },
        "aspect_ratio": {
            "type": "string",
            "enum": ["16:9", "9:16"],
            "description": "16:9 for landscape (default), 9:16 for portrait/vertical",
            "default": "16:9"
        },
        "duration": {
            "type": "integer",
            "enum": [4, 6, 8],
            "description": "Video duration in seconds. 8s required for 1080p.",
            "default": 8
        },
        "resolution": {
            "type": "string",
            "enum": ["720p", "1080p"],
            "description": "720p (default) or 1080p (Veo 3.1 only, requires 8s duration)",
            "default": "720p"
        },
        "negative_prompt": {
            "type": "string",
            "description": "What NOT to include (e.g., 'cartoon, low quality, blurry'). Don't use 'no' or 'don't'."
        },
        "output_path": {
            "type": "string",
            "description": "Path to save video (.mp4). If not provided, saves to /tmp/"
        }
    },
    "required": ["prompt"]
}


@tool(
    name="gemini_generate_video",
    description="Generate a video using Google Veo 3.1 with native audio. Creates 4-8 second 720p/1080p videos with realistic motion, dialogue, and sound effects. Use descriptive prompts including subject, action, style, camera motion.",
    input_schema=GENERATE_VIDEO_SCHEMA,
    tags=["media", "video"]
)
def generate_video(
    prompt: str,
    model: str = "veo31",
    aspect_ratio: str = "16:9",
    duration: int = 8,
    resolution: str = "720p",
    negative_prompt: Optional[str] = None,
    output_path: Optional[str] = None
) -> str:
    """
    Generate video using Google Veo 3.1 - state-of-the-art video generation with native audio.
    """
    try:
        model_id = VIDEO_MODELS.get(model, VIDEO_MODELS["veo31"])

        # Build config
        config_params = {
            "aspect_ratio": aspect_ratio,
            "duration_seconds": str(duration),
        }

        # Resolution only for Veo 3.1 (1080p requires 8s duration)
        if model in ["veo31", "veo31_fast"]:
            if resolution == "1080p" and duration != 8:
                config_params["resolution"] = "720p"  # 1080p requires 8s
            else:
                config_params["resolution"] = resolution

        # Add negative prompt if provided
        if negative_prompt:
            config_params["negative_prompt"] = negative_prompt

        # Person generation - required for Veo
        config_params["person_generation"] = "allow_all"

        log_progress(f"Starting video generation with {model_id} ({duration}s, {resolution})...")
        log_progress("This may take 1-6 minutes...")

        # Start video generation
        operation = client.models.generate_videos(
            model=model_id,
            prompt=prompt,
            config=types.GenerateVideosConfig(**config_params)
        )

        # Poll for completion (video generation can take 1-6 minutes)
        max_wait = 360  # 6 minutes max
        poll_interval = 10

        # Sync polling - async version caused deadlocks in FastMCP
        elapsed = 0
        while not operation.done and elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            log_progress(f"Video generation in progress... ({elapsed}s elapsed)")
            operation = client.operations.get(operation)

        if not operation.done:
            log_progress("Video generation timed out")
            return f"Video generation timed out after {max_wait} seconds. Operation may still be running."

        log_progress("Video generation completed")

        # Check for errors
        if hasattr(operation, 'error') and operation.error:
            return f"Video generation failed: {operation.error}"

        # Get generated video
        if not hasattr(operation, 'response') or not operation.response:
            return "Video generation completed but no response received."

        generated_videos = operation.response.generated_videos
        if not generated_videos:
            return "No video was generated. Try a different prompt."

        video = generated_videos[0]

        # Download the video
        client.files.download(file=video.video)

        if output_path:
            # Ensure .mp4 extension
            if not output_path.endswith('.mp4'):
                output_path = output_path.rsplit('.', 1)[0] + '.mp4' if '.' in output_path else output_path + '.mp4'

            video.video.save(output_path)

            return f"""Video generated successfully!
- Saved to: {output_path}
- Model: {model_id}
- Duration: {duration}s
- Resolution: {resolution}
- Aspect ratio: {aspect_ratio}
- Has audio: Yes"""
        else:
            # Save to temp location and return info
            temp_path = f"/tmp/gemini_video_{int(time.time())}.mp4"
            video.video.save(temp_path)

            return f"""Video generated successfully!
- Temporary file: {temp_path}
- Model: {model_id}
- Duration: {duration}s
- Resolution: {resolution}
- Aspect ratio: {aspect_ratio}
- Has audio: Yes

Note: Specify output_path to save to a custom location."""

    except Exception as e:
        return f"Video generation error: {str(e)}"
