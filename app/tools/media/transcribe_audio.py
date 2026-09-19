"""
Transcribe Audio Tool (v4.7.0)

Speech-to-text with Gemini's dedicated transcription models (gemini-X.Y-transcribe):
85+ languages auto-detected, speaker diarization, word-level timestamps, custom
vocabulary, smart (cleaned) or verbatim output. Audio up to 1 hour per request
(30 minutes when diarization or timestamps are on — upstream limit).

Requires google-genai >= 2.20.0 (GenerateContentConfig.audio_transcription_config).
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from ...tools.registry import tool
from ...services import client, types, is_available, get_error
from ...services.model_registry import model_registry
from ...core import log_progress


AUDIO_MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
    ".aiff": "audio/aiff",
    ".aif": "audio/aiff",
    ".webm": "audio/webm",
}

INLINE_LIMIT_BYTES = 15 * 1024 * 1024   # above this, go through the Files API (inline cap is 20 MB)
FILE_ACTIVE_TIMEOUT_SECONDS = 180       # Files API processing wait
MODES = {"smart": "SMART", "verbatim": "VERBATIM"}
AUTO_MODE = "auto"   # smart, or verbatim when word timestamps are requested (SMART + timestamps is a 400 upstream)
SENTENCE_END = (".", "?", "!", "…")

TRANSCRIBE_AUDIO_SCHEMA = {
    "type": "object",
    "properties": {
        "audio_path": {
            "type": "string",
            "description": "Local path to the audio file (wav, mp3, m4a, aac, ogg, opus, flac, aiff, webm). Up to 1 hour; 30 minutes when diarization or word_timestamps are on."
        },
        "diarization": {
            "type": "boolean",
            "description": "Label speakers (up to 8; 3+ is experimental upstream). Incompatible with vocabulary.",
            "default": False
        },
        "word_timestamps": {
            "type": "boolean",
            "description": "Word-level timestamps; the transcript is then returned as timestamped sentences.",
            "default": False
        },
        "language_codes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional BCP-47 hints, e.g. ['it', 'en']. Omit for auto-detection (85+ languages, code-switching handled)."
        },
        "vocabulary": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Domain terms and names to bias recognition toward (e.g. ['MCP', 'Anthropic']). Not combinable with diarization."
        },
        "mode": {
            "type": "string",
            "enum": ["auto", "smart", "verbatim"],
            "description": "auto (default): smart, or verbatim when word_timestamps is on (the API rejects smart + timestamps). smart: fillers removed, numbers/dates/alphanumerics formatted. verbatim: exactly what was said.",
            "default": "auto"
        },
        "output_path": {
            "type": "string",
            "description": "Optional file to save the transcript. '.json' → structured (text, segments, words); anything else → the formatted text."
        }
    },
    "required": ["audio_path"]
}


def resolve_model() -> str:
    """Transcription model for this call (env override > auto-detect > fallback)."""
    return model_registry.resolve("transcribe")


def build_transcription_config(
    diarization: bool,
    word_timestamps: bool,
    language_codes: Optional[List[str]],
    vocabulary: Optional[List[str]],
    mode: str,
) -> Dict[str, Any]:
    """Kwargs for types.AudioTranscriptionConfig, validated for the upstream constraints."""
    if mode == AUTO_MODE:
        mode = "verbatim" if word_timestamps else "smart"
    if mode not in MODES:
        raise ValueError(f"mode must be one of {[AUTO_MODE, *sorted(MODES)]} (got {mode!r})")
    if diarization and vocabulary:
        raise ValueError("diarization and vocabulary cannot be combined (upstream limitation)")
    if word_timestamps and mode == "smart":
        raise ValueError("mode='smart' is incompatible with word_timestamps (upstream limitation): use mode='verbatim' or 'auto'")
    cfg: Dict[str, Any] = {"mode": MODES[mode]}
    if diarization:
        cfg["diarization"] = True
    if word_timestamps:
        cfg["word_timestamp"] = True
    if language_codes:
        cfg["language_codes"] = [c.strip() for c in language_codes if c and c.strip()]
    if vocabulary:
        cfg["custom_vocabulary"] = [v.strip() for v in vocabulary if v and v.strip()]
    return cfg


def _seconds(offset: Any) -> Optional[float]:
    """'12.300s' | 12.3 | timedelta → seconds."""
    if offset is None:
        return None
    if hasattr(offset, "total_seconds"):
        return float(offset.total_seconds())
    if isinstance(offset, (int, float)):
        return float(offset)
    text = str(offset).rstrip("s")
    try:
        return float(text)
    except ValueError:
        return None


def _stamp(seconds: Optional[float]) -> str:
    if seconds is None:
        return "??:??"
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes):02d}:{rest:04.1f}"


def parse_transcription(response: Any) -> Dict[str, Any]:
    """
    Normalise the SDK response into {text, segments, words}.

    Every part carries `audio_transcription` (text, speaker_label, language_code,
    words[{word, start_offset, end_offset}]). `response.text` is NOT reliable: it
    is empty when no options are set. Multiple parts = multiple speakers/chunks.
    """
    parts_out: List[Dict[str, Any]] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            at = getattr(part, "audio_transcription", None)
            if at is None:
                continue
            words = [
                {
                    "word": getattr(w, "word", "") or "",
                    "start": _seconds(getattr(w, "start_offset", None)),
                    "end": _seconds(getattr(w, "end_offset", None)),
                    "speaker": getattr(w, "speaker_label", None),
                }
                for w in (getattr(at, "words", None) or [])
            ]
            parts_out.append({
                "text": (getattr(at, "text", None) or "").strip(),
                "speaker": getattr(at, "speaker_label", None),
                "language": getattr(at, "language_code", None),
                "words": words,
            })

    text = "\n".join(p["text"] for p in parts_out if p["text"])
    languages = sorted({p["language"] for p in parts_out if p["language"]})
    return {
        "text": text,
        "languages": languages,
        "segments": _segments(parts_out),
        "words": [w for p in parts_out for w in p["words"]],
    }


def _segments(parts_out: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sentence-level segments with speaker and start/end, built from words when present."""
    segments: List[Dict[str, Any]] = []
    for part in parts_out:
        if not part["words"]:
            if part["text"]:
                segments.append({"speaker": part["speaker"], "start": None, "end": None, "text": part["text"]})
            continue
        current: List[Dict[str, Any]] = []
        for word in part["words"]:
            speaker = word["speaker"] or part["speaker"]
            if current and current[-1]["speaker"] != speaker:
                segments.append(_flush(current))
                current = []
            current.append({**word, "speaker": speaker})
            if word["word"].endswith(SENTENCE_END):
                segments.append(_flush(current))
                current = []
        if current:
            segments.append(_flush(current))
    return segments


def _flush(words: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "speaker": words[0]["speaker"],
        "start": words[0]["start"],
        "end": words[-1]["end"],
        "text": " ".join(w["word"] for w in words),
    }


def format_transcript(result: Dict[str, Any], diarization: bool, word_timestamps: bool) -> str:
    """Human-readable transcript: plain text, or one line per segment with speaker/time."""
    if not (diarization or word_timestamps) or not result["segments"]:
        return result["text"]
    lines = []
    for seg in result["segments"]:
        prefix = ""
        if word_timestamps and seg["start"] is not None:
            prefix += f"[{_stamp(seg['start'])}] "
        if diarization and seg["speaker"]:
            prefix += f"{seg['speaker']}: "
        lines.append(prefix + seg["text"])
    return "\n".join(lines)


def _audio_part(audio_path: str, mime_type: str):
    """Inline bytes for small files; Files API (upload + wait ACTIVE) for large ones."""
    size = os.path.getsize(audio_path)
    if size <= INLINE_LIMIT_BYTES:
        with open(audio_path, "rb") as fh:
            return types.Part.from_bytes(data=fh.read(), mime_type=mime_type), None

    log_progress(f"transcribe_audio: {size // (1024 * 1024)} MB → uploading via Files API")
    uploaded = client.files.upload(file=audio_path, config={"mime_type": mime_type})
    deadline = time.time() + FILE_ACTIVE_TIMEOUT_SECONDS
    while _state_name(uploaded) not in ("ACTIVE", "FAILED") and time.time() < deadline:
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)
    if _state_name(uploaded) != "ACTIVE":
        raise RuntimeError(f"Files API did not make the upload ACTIVE in time (state={_state_name(uploaded)})")
    return types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type or mime_type), uploaded.name


def _state_name(uploaded: Any) -> str:
    state = getattr(uploaded, "state", None)
    return getattr(state, "name", None) or str(state or "")


def _save(output_path: str, result: Dict[str, Any], formatted: str, model_id: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    if output_path.lower().endswith(".json"):
        payload = {"model": model_id, **result}
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    else:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(formatted + "\n")
    return output_path


@tool(
    name="gemini_transcribe_audio",
    description="Transcribe an audio file (speech to text) with Gemini's dedicated transcription model: 85+ languages auto-detected, optional speaker diarization, word-level timestamps, custom vocabulary, smart or verbatim mode. Up to 1 hour of audio.",
    input_schema=TRANSCRIBE_AUDIO_SCHEMA,
    tags=["media", "audio", "transcription"]
)
def transcribe_audio(
    audio_path: str,
    diarization: bool = False,
    word_timestamps: bool = False,
    language_codes: Optional[List[str]] = None,
    vocabulary: Optional[List[str]] = None,
    mode: str = AUTO_MODE,
    output_path: Optional[str] = None,
) -> str:
    """
    Speech-to-text with the newest gemini-*-transcribe model the API exposes.

    Returns the transcript (one line per speaker/sentence when diarization or
    timestamps are on) with a header naming the model and detected language(s).
    """
    if not is_available():
        return f"Error: {get_error()}"
    if not os.path.isfile(audio_path):
        return f"Error: audio file not found: {audio_path}"
    ext = os.path.splitext(audio_path)[1].lower()
    mime_type = AUDIO_MIME_TYPES.get(ext)
    if not mime_type:
        return f"Error: unsupported audio format '{ext}'. Supported: {', '.join(sorted(AUDIO_MIME_TYPES))}"

    try:
        cfg_kwargs = build_transcription_config(diarization, word_timestamps, language_codes, vocabulary, mode)
    except ValueError as e:
        return f"Error: {e}"

    model_id = resolve_model()
    uploaded_name = None
    try:
        if not hasattr(types, "AudioTranscriptionConfig") or \
                "audio_transcription_config" not in types.GenerateContentConfig.model_fields:
            return (
                "Error: this google-genai SDK has no audio_transcription_config. "
                "Required: google-genai >= 2.20.0 (pip install -U google-genai)."
            )

        part, uploaded_name = _audio_part(audio_path, mime_type)
        log_progress(f"transcribe_audio: {os.path.basename(audio_path)} with {model_id} ({cfg_kwargs})")

        response = client.models.generate_content(
            model=model_id,
            contents=[part],
            config=types.GenerateContentConfig(
                audio_transcription_config=types.AudioTranscriptionConfig(**cfg_kwargs)
            ),
        )
        result = parse_transcription(response)
        if not result["text"]:
            return f"Transcription returned no text (model {model_id}). Is the file speech audio?"

        formatted = format_transcript(result, diarization, word_timestamps)
        header = f"[Transcribed with {model_id} · mode={cfg_kwargs['mode'].lower()}"
        if result["languages"]:
            header += f" · language={'/'.join(result['languages'])}"
        if result["words"]:
            header += f" · {len(result['words'])} words"
        header += "]"

        saved = ""
        if output_path:
            saved = f"\n\n*Saved to: {_save(output_path, result, formatted, model_id)}*"
        return f"{header}\n\n{formatted}{saved}"

    except Exception as e:
        return f"Transcription error ({model_id}): {e}"
    finally:
        if uploaded_name:
            try:
                client.files.delete(name=uploaded_name)
            except Exception:
                pass
