"""
Text-to-Speech Tool (Gemini 3.8 TTS via the Interactions API, v4.8.0)

- Models: flash = newest Gemini Flash TTS (3.8: studio-grade, acting, dialects),
  lite = newest Flash-Lite TTS (fast, cost-efficient), pro = alias of flash.
- Voices: any of the 30 featured studio voices, any voice of the Extended Voice
  Library (see gemini_list_voices), a designed voice ID (voice_...) or a
  replicated voice ID/key (voice_... / voicekey_...).
- Style: natural-language direction per request or per speaker turn
  (speech_metadata annotations), e.g. "cheerful and friendly", "whispering".
- Output: WAV (24 kHz mono). Raw PCM responses are wrapped into WAV.
"""

import io
import os
import re
import time
import wave
from typing import Dict, List, Optional

from ...tools.registry import tool
from ...services import TTS_MODELS, TTS_VOICES, is_available, get_error
from ...services import interactions as ix

FEATURED_VOICES = ", ".join(TTS_VOICES)
MAX_SPEAKERS = 2
TTS_TIMEOUT_SECONDS = 300
PCM_MIMES = ("audio/l16", "audio/pcm")
DEFAULT_SAMPLE_RATE = 24000

TTS_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "Exact text to speak. For two speakers write one turn per line: 'Name: what they say'."
        },
        "voice": {
            "type": "string",
            "description": f"Voice: a featured studio voice ({FEATURED_VOICES}), any Voice Library ID from gemini_list_voices, or a custom voice_... / voicekey_... ID.",
            "default": "Kore"
        },
        "style": {
            "type": "string",
            "description": "Optional delivery direction in plain words: 'cheerful and friendly', 'slow, warm audiobook narration', 'whispering'."
        },
        "language": {
            "type": "string",
            "description": "Optional BCP-47 language of the voice, e.g. 'it-IT'."
        },
        "model": {
            "type": "string", "enum": ["flash", "lite", "pro"], "default": "flash",
            "description": "flash (default): newest Flash TTS, best fidelity and acting. lite: newest Flash-Lite TTS, fastest/cheapest. pro: alias of flash."
        },
        "speakers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "voice": {"type": "string"},
                    "style": {"type": "string"}
                },
                "required": ["name", "voice"]
            },
            "description": "Two-speaker dialogue: [{\"name\": \"Joe\", \"voice\": \"Puck\", \"style\": \"cheerful\"}, {\"name\": \"Jane\", \"voice\": \"Kore\"}]."
        },
        "output_path": {"type": "string", "description": "Where to save the .wav (default /tmp)."}
    },
    "required": ["text"]
}


def parse_dialogue(text: str, names: List[str]) -> List[Dict[str, str]]:
    """Split 'Name: utterance' lines into turns; lines without a known name continue the previous turn."""
    turns: List[Dict[str, str]] = []
    pattern = re.compile(rf"^\s*({'|'.join(re.escape(n) for n in names)})\s*:\s*(.*)$")
    for line in text.splitlines():
        if not line.strip():
            continue
        match = pattern.match(line)
        if match:
            turns.append({"speaker": match.group(1), "text": match.group(2).strip()})
        elif turns:
            turns[-1]["text"] += " " + line.strip()
    return [t for t in turns if t["text"]]


def build_tts_request(
    model_id: str,
    text: str,
    voice: str,
    style: Optional[str],
    language: Optional[str],
    speakers: Optional[List[Dict[str, str]]],
) -> dict:
    """Interactions create() kwargs (validated in tests against the SDK schema)."""
    if speakers and len(speakers) >= 2:
        speakers = speakers[:MAX_SPEAKERS]
        names = [s["name"] for s in speakers]
        styles = {s["name"]: s.get("style") for s in speakers}
        turns = parse_dialogue(text, names)
        if not turns:
            raise ValueError(f"no dialogue lines found: write each turn as '{names[0]}: ...'")
        content = []
        for turn in turns:
            meta = {"type": "speech_metadata", "speaker": turn["speaker"]}
            if styles.get(turn["speaker"]):
                meta["style"] = styles[turn["speaker"]]
            content.append({"type": "text", "text": turn["text"], "annotations": [meta]})
        speech_config = {"speakers": [{"speaker": s["name"], "voice": s["voice"]} for s in speakers]}
    else:
        item = {"type": "text", "text": text}
        if style:
            item["annotations"] = [{"type": "speech_metadata", "style": style}]
        content = [item]
        voice_cfg = {"voice": voice or "Kore"}
        if language:
            voice_cfg["language"] = language
        speech_config = [voice_cfg]
    return {
        "model": model_id,
        "input": [{"type": "user_input", "content": content}],
        "generation_config": {"speech_config": speech_config},
    }


def wav_bytes(audio: bytes, mime: str, sample_rate: Optional[int]) -> bytes:
    """Return a WAV file: pass WAV through, wrap raw 16-bit PCM."""
    if audio[:4] == b"RIFF" or (mime and "wav" in mime):
        return audio
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate or DEFAULT_SAMPLE_RATE)
        wf.writeframes(audio)
    return buf.getvalue()


def wav_duration(data: bytes) -> Optional[float]:
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return None


@tool(
    name="gemini_text_to_speech",
    description=(
        "Convert text to speech with Gemini 3.8 TTS: studio-grade single-voice or two-speaker dialogue, "
        "any featured, Voice Library, designed or replicated voice, per-turn style direction (emotion, pace, accent). "
        "Saves a WAV file."
    ),
    input_schema=TTS_SCHEMA,
    tags=["media", "audio"]
)
def text_to_speech(
    text: str,
    voice: str = "Kore",
    model: str = "flash",
    speakers: Optional[List[Dict[str, str]]] = None,
    output_path: Optional[str] = None,
    style: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """Generate speech from text (single voice or two-speaker dialogue)."""
    if not is_available():
        return f"Error: {get_error()}"
    try:
        model_id = TTS_MODELS[model] if model in TTS_MODELS else TTS_MODELS["flash"]
        request = build_tts_request(model_id, text, voice, style, language, speakers)
        interaction = ix.run(request, TTS_TIMEOUT_SECONDS)
        item = ix.output_media(interaction, "audio")
        if item is None:
            return f"TTS returned no audio. Model said: {ix.output_text(interaction) or 'nothing'}"

        audio = wav_bytes(ix.media_bytes(item), ix._get(item, "mime_type") or "", ix._get(item, "sample_rate"))
        if not output_path:
            output_path = f"/tmp/gemini_tts_{int(time.time())}.wav"
        elif not output_path.lower().endswith(".wav"):
            output_path = os.path.splitext(output_path)[0] + ".wav"
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as fh:
            fh.write(audio)

        duration = wav_duration(audio)
        multi = bool(speakers and len(speakers) >= 2)
        voices = ", ".join(f"{s['name']}: {s['voice']}" for s in speakers[:MAX_SPEAKERS]) if multi else voice
        lines = [
            "Audio generated successfully!",
            f"- Saved to: {output_path}",
            f"- Model: {model_id}",
            f"- Mode: {'Two-speaker dialogue' if multi else 'Single voice'}",
            f"- Voice(s): {voices}",
        ]
        if style and not multi:
            lines.append(f"- Style: {style}")
        if duration:
            lines.append(f"- Duration: {duration:.1f}s")
        return "\n".join(lines)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"TTS generation error: {e}"
