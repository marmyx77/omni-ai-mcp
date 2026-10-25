"""
Voice Library tools (Gemini API Voices endpoint, v4.8.0)

- gemini_list_voices: browse the Extended Voice Library (hundreds of voices) and
  your own designed/replicated voices, with filters.
- gemini_design_voice: create a persistent custom voice from a text description
  (voice_... ID + WAV preview).
- gemini_replicate_voice: replicate a real speaker's voice from a 10-30 s
  reference clip plus a consent recording of the SAME adult speaker reading
  Google's mandatory consent statement. Google verifies the consent server-side.

Voices are usable in gemini_text_to_speech with the 3.8 TTS models.
Requires google-genai >= 2.25.0 (client.voices).
"""

import base64
import os
import time
import wave
from typing import Any, Dict, List, Optional

from ...tools.registry import tool
from ...services import client, TTS_MODELS, is_available, get_error
from ...core.security import safe_input_path, safe_output_path, default_output_path

GENDERS = ("female", "male", "neutral")
PITCHES = ("low", "medium", "high")
VOICE_TYPES = ("prebuilt", "prompted", "replicated")
MAX_PAGE_SIZE = 1000
REFERENCE_SECONDS = (10, 30)
CONSENT_STATEMENT_EN = (
    "I am the owner of this voice and I consent to Google using this voice to create a synthetic voice model."
)


def _get(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _voices_api():
    if not hasattr(client, "voices"):
        raise RuntimeError("this google-genai SDK has no Voices API. Required: google-genai >= 2.25.0")
    return client.voices


def _as_list(value: Optional[Any]) -> Optional[List[str]]:
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v) for v in value]


def build_list_filters(
    language_codes=None, gender=None, pitch=None, accent=None, persona=None,
    contexts=None, voice_type=None, search=None, page_size: int = 50, page_token=None,
) -> Dict[str, Any]:
    """Keyword arguments for client.voices.list (lists combine with OR, filters with AND)."""
    filters: Dict[str, Any] = {}
    for key, value in (("language_code", language_codes), ("gender", gender), ("pitch", pitch),
                       ("accent", accent), ("persona", persona), ("contexts", contexts), ("type_", voice_type)):
        items = _as_list(value)
        if items:
            filters[key] = items
    for bad in [g for g in filters.get("gender", []) if g not in GENDERS]:
        raise ValueError(f"gender '{bad}' not in {GENDERS}")
    for bad in [p for p in filters.get("pitch", []) if p not in PITCHES]:
        raise ValueError(f"pitch '{bad}' not in {PITCHES}")
    for bad in [t for t in filters.get("type_", []) if t not in VOICE_TYPES]:
        raise ValueError(f"voice_type '{bad}' not in {VOICE_TYPES}")
    if search:
        filters["search"] = search
    filters["page_size"] = max(1, min(int(page_size), MAX_PAGE_SIZE))
    if page_token:
        filters["page_token"] = page_token
    return filters


def format_voice(voice: Any) -> str:
    details = [x for x in (_get(voice, "language_code"), _get(voice, "accent"), _get(voice, "gender"),
                           f"pitch={_get(voice, 'pitch')}" if _get(voice, "pitch") else None) if x]
    persona = _get(voice, "persona") or _get(voice, "description") or ""
    line = f"- `{_get(voice, 'id')}` {_get(voice, 'display_name') or ''}"
    if details:
        line += f" ({', '.join(str(d) for d in details)})"
    if persona:
        line += f": {str(persona)[:120]}"
    return line


@tool(
    name="gemini_list_voices",
    description=(
        "Browse Gemini's Extended Voice Library (hundreds of TTS voices across languages, accents, personas) plus your "
        "designed and replicated voices. Filter by language, gender, pitch, accent, persona, usage context, type or text. "
        "Use the returned ID as `voice` in gemini_text_to_speech."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "language_codes": {"type": "array", "items": {"type": "string"}, "description": "BCP-47, e.g. ['it-IT']"},
            "gender": {"type": "array", "items": {"type": "string", "enum": list(GENDERS)}},
            "pitch": {"type": "array", "items": {"type": "string", "enum": list(PITCHES)}},
            "accent": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['British']"},
            "persona": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['Narrator']"},
            "contexts": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['Audiobook', 'News']"},
            "voice_type": {"type": "array", "items": {"type": "string", "enum": list(VOICE_TYPES)}},
            "search": {"type": "string", "description": "Free text matched against name and description"},
            "page_size": {"type": "integer", "default": 50, "minimum": 1, "maximum": MAX_PAGE_SIZE},
            "page_token": {"type": "string"}
        }
    },
    tags=["media", "audio", "voices"]
)
def list_voices(
    language_codes: Optional[List[str]] = None,
    gender: Optional[List[str]] = None,
    pitch: Optional[List[str]] = None,
    accent: Optional[List[str]] = None,
    persona: Optional[List[str]] = None,
    contexts: Optional[List[str]] = None,
    voice_type: Optional[List[str]] = None,
    search: Optional[str] = None,
    page_size: int = 50,
    page_token: Optional[str] = None,
) -> str:
    """List voices of the Gemini Voice Library."""
    if not is_available():
        return f"Error: {get_error()}"
    try:
        filters = build_list_filters(language_codes, gender, pitch, accent, persona, contexts,
                                     voice_type, search, page_size, page_token)
        response = _voices_api().list(**filters)
        voices = list(_get(response, "voices") or [])
        if not voices:
            return "No voices match these filters."
        lines = [f"**{len(voices)} voices**"] + [format_voice(v) for v in voices]
        next_token = _get(response, "next_page_token")
        if next_token:
            lines.append(f"\n*More results: page_token='{next_token}'*")
        return "\n".join(lines)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Voice listing error: {e}"


def _save_preview(voice: Any, preview_path: Optional[str], stem: str) -> Optional[str]:
    sample = _get(voice, "sample_audio")
    data = _get(sample, "data") if sample else None
    if not data:
        return None
    path = safe_output_path(preview_path, {".wav"}) if preview_path else default_output_path(stem, ".wav")
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(data) if isinstance(data, str) else bytes(data))
    return path


def build_design_request(model_id: str, description: str, display_name: str,
                         gender: Optional[str], language_code: Optional[str]) -> Dict[str, Any]:
    if not description or len(description.strip()) < 10:
        raise ValueError("describe the voice in at least a sentence (age, timbre, accent, attitude)")
    if gender and gender not in GENDERS:
        raise ValueError(f"gender must be one of {GENDERS}")
    voice: Dict[str, Any] = {
        "model": model_id,
        "type": "prompted",
        "display_name": display_name or "Custom voice",
        "prompted": {"input": description.strip()},
    }
    if gender:
        voice["gender"] = gender
    if language_code:
        voice["language_code"] = language_code
    return {"store": True, "voice": voice}


@tool(
    name="gemini_design_voice",
    description=(
        "Create a persistent custom TTS voice from a plain-language description (age, timbre, accent, attitude). "
        "Returns a voice_... ID for gemini_text_to_speech and saves a WAV preview. Stored voices: max 200 per project, 1-year retention."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "e.g. 'A warm, thoughtful astronomer in his late 60s with a gentle British accent, speaking with quiet wonder.'"},
            "display_name": {"type": "string"},
            "gender": {"type": "string", "enum": list(GENDERS)},
            "language_code": {"type": "string", "description": "BCP-47, e.g. 'it-IT'"},
            "model": {"type": "string", "enum": ["flash", "lite"], "default": "flash"},
            "preview_path": {"type": "string", "description": "Where to save the WAV preview, inside the workspace (default: a private temp folder, or GEMINI_OUTPUT_DIR)"}
        },
        "required": ["description"]
    },
    tags=["media", "audio", "voices"]
)
def design_voice(
    description: str,
    display_name: str = "Custom voice",
    gender: Optional[str] = None,
    language_code: Optional[str] = None,
    model: str = "flash",
    preview_path: Optional[str] = None,
) -> str:
    """Design a new persistent voice from a description."""
    if not is_available():
        return f"Error: {get_error()}"
    try:
        model_id = TTS_MODELS["lite" if model == "lite" else "flash"]
        created = _voices_api().create(**build_design_request(model_id, description, display_name, gender, language_code))
        preview = _save_preview(created, preview_path, "gemini_voice_preview")
        lines = ["Voice created.", f"- Voice ID: `{_get(created, 'id')}`  (use it as `voice` in gemini_text_to_speech)",
                 f"- Model: {model_id}"]
        if preview:
            lines.append(f"- Preview: {preview}")
        return "\n".join(lines)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Voice design error: {e}"


def _wav_seconds(path: str) -> Optional[float]:
    try:
        with wave.open(path, "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return None


def build_replication_request(model_id: str, source_path: str, consent_path: str,
                              display_name: str, store: bool) -> Dict[str, Any]:
    checked = []
    for label, path in (("source_audio_path", source_path), ("consent_audio_path", consent_path)):
        try:
            checked.append(safe_input_path(path, allowed_extensions={".wav"}))
        except ValueError as e:
            if "unsupported file type" in str(e):
                raise ValueError(f"{label} must be a WAV file (24 kHz mono 16-bit recommended)")
            raise ValueError(f"{label}: {e}")
    source_path, consent_path = checked
    seconds = _wav_seconds(source_path)
    low, high = REFERENCE_SECONDS
    if seconds is not None and not (low - 0.5) <= seconds <= (high + 0.5):
        raise ValueError(f"reference clip is {seconds:.1f}s: it must be {low}-{high} s of clean natural speech")

    def audio(path: str) -> Dict[str, str]:
        with open(path, "rb") as fh:
            return {"mime_type": "audio/wav", "data": base64.b64encode(fh.read()).decode("ascii")}

    return {
        "store": bool(store),
        "voice": {
            "model": model_id,
            "type": "replicated",
            "display_name": display_name or "Replicated voice",
            "replicated": {"source_audio": audio(source_path), "consent_audio": audio(consent_path)},
        },
    }


@tool(
    name="gemini_replicate_voice",
    description=(
        "Replicate a real speaker's voice for TTS from a 10-30 s reference WAV plus a consent WAV in which the SAME adult "
        f"speaker reads Google's consent statement (English: \"{CONSENT_STATEMENT_EN}\"). Google verifies consent and rejects "
        "mismatches. store=true returns a persistent voice_... ID; store=false returns a stateless voicekey_... you keep locally."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "source_audio_path": {"type": "string", "description": "10-30 s WAV of clean natural speech"},
            "consent_audio_path": {"type": "string", "description": "WAV of the same speaker reading the consent statement"},
            "display_name": {"type": "string"},
            "store": {"type": "boolean", "default": True},
            "model": {"type": "string", "enum": ["flash", "lite"], "default": "flash"}
        },
        "required": ["source_audio_path", "consent_audio_path"]
    },
    tags=["media", "audio", "voices"]
)
def replicate_voice(
    source_audio_path: str,
    consent_audio_path: str,
    display_name: str = "Replicated voice",
    store: bool = True,
    model: str = "flash",
) -> str:
    """Replicate a consenting speaker's voice."""
    if not is_available():
        return f"Error: {get_error()}"
    try:
        model_id = TTS_MODELS["lite" if model == "lite" else "flash"]
        request = build_replication_request(model_id, source_audio_path, consent_audio_path, display_name, store)
        created = _voices_api().create(**request)
        if store:
            ident = _get(created, "id")
            return f"Voice replicated.\n- Voice ID: `{ident}` (persistent, 1-year retention)\n- Model: {model_id}"
        key = _get(created, "key")
        return (f"Voice replicated (stateless).\n- Voice key: `{key}`\n"
                "- Google stores nothing: keep this key safe and pass it as `voice` in gemini_text_to_speech.")
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Voice replication error: {e}"
