"""
Generate Music Tool (Lyria, v4.8.0)

- full (default): newest Lyria (3.5) — full-length songs with verses, choruses,
  bridges, natural vocals and timed lyrics; length steerable in the prompt
  (typically a couple of minutes).
- clip: Lyria 3 Clip — always a 30-second clip (loops, jingles, previews).

Input: text prompt, optionally one or more images to inspire the music.
Output: MP3, 44.1 kHz stereo, plus the generated lyrics / song structure.
"""

from typing import List, Optional

from ...tools.registry import tool
from ...services import MUSIC_MODELS, is_available, get_error
from ...services import interactions as ix

POLL_SECONDS = 5

GENERATE_MUSIC_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": (
                "Describe the music: genre, mood, instruments, tempo, vocals (or 'instrumental'), language of the lyrics, "
                "structure and length (e.g. 'about 2 minutes, verse-chorus-verse-chorus-bridge-chorus'). "
                "You can also give your own lyrics."
            )
        },
        "image_paths": {
            "type": "array", "items": {"type": "string"},
            "description": "Optional images to inspire the music (mood, scene, artwork)."
        },
        "model": {
            "type": "string", "enum": ["full", "clip"], "default": "full",
            "description": "full: newest Lyria, full-length songs. clip: 30-second clip."
        },
        "output_path": {"type": "string", "description": "Where to save the .mp3, inside the workspace (default: a private temp folder, or GEMINI_OUTPUT_DIR)."},
        "retrieve_id": {"type": "string", "description": "interaction_id of a generation that timed out: fetch and save it (waits if still running)."},
        "max_wait_minutes": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10}
    },
    "required": ["prompt"]
}


def build_music_request(model_id: str, prompt: str, image_blocks: List[dict]) -> dict:
    if not prompt or not prompt.strip():
        raise ValueError("prompt is required")
    text = {"type": "text", "text": prompt.strip()}
    return {
        "model": model_id,
        "input": list(image_blocks) + [text] if image_blocks else prompt.strip(),
        "background": True,
    }


def _result(interaction, output_path: Optional[str], model_id: str) -> str:
    item = ix.output_media(interaction, "audio")
    lyrics = ix.output_text(interaction)
    if item is None:
        return f"No audio returned (interaction {ix._get(interaction, 'id')}). Model said: {lyrics or 'nothing'}"
    path, size = ix.save_media(item, output_path, "gemini_music")
    lines = [
        "Music generated successfully!",
        f"- Saved to: {path} ({size // 1024} KB)",
        f"- Model: {ix._get(interaction, 'model') or model_id}",
    ]
    if lyrics:
        lines += ["", "**Lyrics / structure:**", lyrics.strip()]
    return "\n".join(lines)


@tool(
    name="gemini_generate_music",
    description=(
        "Generate music with Google Lyria: full-length songs with vocals and lyrics (Lyria 3.5) or 30-second clips, "
        "from a text prompt and optional inspiration images. Saves an MP3 (44.1 kHz stereo) and returns the lyrics."
    ),
    input_schema=GENERATE_MUSIC_SCHEMA,
    tags=["media", "audio", "music"]
)
def generate_music(
    prompt: str,
    image_paths: Optional[List[str]] = None,
    model: str = "full",
    output_path: Optional[str] = None,
    max_wait_minutes: int = 10,
    retrieve_id: Optional[str] = None,
) -> str:
    """Generate a song or clip with Lyria."""
    if not is_available():
        return f"Error: {get_error()}"
    uploaded: List[Optional[str]] = []
    timeout = max(1, int(max_wait_minutes)) * 60
    try:
        model_id = MUSIC_MODELS["clip" if model == "clip" else "full"]
        if retrieve_id:
            return _result(ix.wait(retrieve_id, timeout, POLL_SECONDS), output_path, model_id)
        image_blocks = []
        for img in image_paths or []:
            if ix.kind_for(ix.mime_for(img)) != "image":
                return f"Error: {img} is not an image file"
            block, name = ix.file_block(img)
            image_blocks.append(block)
            uploaded.append(name)

        interaction = ix.run(build_music_request(model_id, prompt, image_blocks), timeout, POLL_SECONDS)
        return _result(interaction, output_path, model_id)
    except FileNotFoundError as e:
        return f"Error: file not found: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except ix.InteractionTimeout as t:
        return (f"Music still generating after {t.waited_seconds // 60} min (it keeps running on Google's side).\n"
                f"Call gemini_generate_music again with retrieve_id='{t.interaction_id}' to save it when ready.")
    except Exception as e:
        return f"Music generation error: {e}"
    finally:
        ix.cleanup(uploaded)
