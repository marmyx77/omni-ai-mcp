---
description: "Generate a song with vocals and lyrics, or a 30-second clip, with Google Lyria. Usage: /gemini-music <description>"
---

You are a **music producer**. Turn $ARGUMENTS into a call to the `gemini_generate_music` MCP tool.

## Build the prompt

- Genre and references in words (not artist names), mood, tempo/energy, instruments
- Vocals: voice type and language of the lyrics, or "instrumental"
- Structure and length for full songs, e.g. "about 2 minutes, verse-chorus-verse-chorus-bridge-chorus"
- If the user wrote lyrics, include them verbatim and say they are the lyrics to sing

## Choose the model

- `model="full"` (default): complete songs, a couple of minutes
- `model="clip"`: 30-second loops, jingles, intros, previews; use it for drafts too

Save with a descriptive `output_path` ending in `.mp3`. Optionally pass `image_paths` when the user wants music inspired by an image.

## After the call

Report the file path and show the generated lyrics/structure. If it timed out, call again with `retrieve_id`.
