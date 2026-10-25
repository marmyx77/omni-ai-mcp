"""
Interactions API helpers (v4.8.0)

Shared plumbing for the tools built on client.interactions (video with Omni
Flash, music with Lyria, TTS 3.8, video understanding, Antigravity agent):
file inputs (inline or Files API), background polling, output extraction from
the 'steps' schema, and saving returned media (inline base64 or URI delivery).

Everything here reads interaction objects through `_get`, which accepts both
SDK models and plain dicts, so the helpers work on SDK responses and on the
fakes used by the unit tests.
"""

import base64
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from ..core import log_progress

INLINE_LIMIT_BYTES = 15 * 1024 * 1024    # above this, upload through the Files API (request cap is 20 MB)
FILE_ACTIVE_TIMEOUT_SECONDS = 300
TERMINAL_OK = ("completed",)
TERMINAL_FAILED = ("failed", "cancelled", "incomplete")

MIME_BY_EXT: Dict[str, str] = {
    # images
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".gif": "image/gif", ".heic": "image/heic", ".heif": "image/heif", ".bmp": "image/bmp",
    ".tif": "image/tiff", ".tiff": "image/tiff",
    # video
    ".mp4": "video/mp4", ".mov": "video/mov", ".mpeg": "video/mpeg", ".mpg": "video/mpg",
    ".avi": "video/avi", ".webm": "video/webm", ".wmv": "video/wmv", ".flv": "video/x-flv",
    ".3gp": "video/3gpp",
    # audio
    ".wav": "audio/wav", ".mp3": "audio/mp3", ".aac": "audio/aac", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".m4a": "audio/m4a", ".aiff": "audio/aiff", ".aif": "audio/aiff",
    ".opus": "audio/opus",
    # documents
    ".pdf": "application/pdf",
}

EXT_BY_MIME: Dict[str, str] = {
    "video/mp4": ".mp4", "video/webm": ".webm", "video/mov": ".mov",
    "audio/mp3": ".mp3", "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/ogg": ".ogg",
    "audio/flac": ".flac", "audio/aac": ".aac", "audio/m4a": ".m4a",
    "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
}


class InteractionTimeout(Exception):
    """The interaction is still running server-side; carries its id for resumption."""

    def __init__(self, interaction_id: str, waited_seconds: int):
        super().__init__(f"interaction {interaction_id} still running after {waited_seconds}s")
        self.interaction_id = interaction_id
        self.waited_seconds = waited_seconds


class InteractionFailed(Exception):
    """The interaction ended in a failed/cancelled state."""


def _get(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _client():
    from .gemini import client
    return client


# ---------------------------------------------------------------- inputs

def mime_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    mime = MIME_BY_EXT.get(ext)
    if not mime:
        raise ValueError(f"unsupported file type '{ext}' for {os.path.basename(path)}")
    return mime


def kind_for(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "document"


def _state(uploaded: Any) -> str:
    state = _get(uploaded, "state")
    return _get(state, "name") or str(state or "")


def upload_and_wait(path: str, mime: str) -> Any:
    """Upload through the Files API and wait until the file is ACTIVE."""
    client = _client()
    uploaded = client.files.upload(file=path, config={"mime_type": mime})
    deadline = time.time() + FILE_ACTIVE_TIMEOUT_SECONDS
    while _state(uploaded) not in ("ACTIVE", "FAILED", "") and time.time() < deadline:
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)
    if _state(uploaded) == "FAILED":
        raise RuntimeError(f"Files API failed to process {os.path.basename(path)}")
    if _state(uploaded) not in ("ACTIVE", ""):
        raise RuntimeError(f"Files API did not finish processing {os.path.basename(path)} in time")
    return uploaded


def file_block(path: str, force_upload: bool = False, **extra: Any) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Content block for a local file: inline base64 when small, Files API URI when large.

    Returns (block, uploaded_name). Delete uploaded_name with cleanup() when done.
    Extra keys (e.g. processing="agentic", resolution="high") are added to the block.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    mime = mime_for(path)
    kind = kind_for(mime)
    size = os.path.getsize(path)
    if force_upload or size > INLINE_LIMIT_BYTES:
        log_progress(f"interactions: uploading {os.path.basename(path)} ({size // 1024} KB) via Files API")
        uploaded = upload_and_wait(path, mime)
        block = {"type": kind, "uri": uploaded.uri, "mime_type": uploaded.mime_type or mime}
        return {**block, **extra}, uploaded.name
    with open(path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("ascii")
    return {"type": kind, "data": data, "mime_type": mime, **extra}, None


def cleanup(uploaded_names: List[Optional[str]]) -> None:
    client = _client()
    for name in uploaded_names:
        if not name:
            continue
        try:
            client.files.delete(name=name)
        except Exception:
            pass


# ------------------------------------------------------------ execution

def wait(interaction_id: str, timeout_seconds: int, poll_seconds: float = 5.0, started: Optional[float] = None) -> Any:
    """Poll interactions.get until a terminal status. Raises InteractionTimeout/InteractionFailed."""
    client = _client()
    started = started or time.time()
    last = None
    while True:
        interaction = client.interactions.get(interaction_id)
        status = _get(interaction, "status") or "unknown"
        if status != last:
            log_progress(f"interactions: {interaction_id[:24]}… status={status} ({int(time.time() - started)}s)")
            last = status
        if status in TERMINAL_OK:
            return interaction
        if status in TERMINAL_FAILED:
            raise InteractionFailed(f"{status}: {_get(interaction, 'error') or 'no error detail'}")
        if time.time() - started > timeout_seconds:
            raise InteractionTimeout(interaction_id, int(time.time() - started))
        time.sleep(poll_seconds)


def run(create_kwargs: Dict[str, Any], timeout_seconds: int, poll_seconds: float = 5.0) -> Any:
    """
    Create an interaction and return it once completed.

    With background=True the server runs it asynchronously and we poll; a
    synchronous call that returns a non-terminal status is polled the same way.
    """
    client = _client()
    started = time.time()
    interaction = client.interactions.create(**create_kwargs)
    status = _get(interaction, "status")
    if status in TERMINAL_OK:
        return interaction
    if status in TERMINAL_FAILED:
        raise InteractionFailed(f"{status}: {_get(interaction, 'error') or 'no error detail'}")
    return wait(_get(interaction, "id"), timeout_seconds, poll_seconds, started)


# --------------------------------------------------------------- outputs

def _model_output_items(interaction: Any) -> List[Any]:
    """Content items of every model_output step after the last user_input, in order."""
    steps = list(_get(interaction, "steps") or [])
    last_user = max((i for i, s in enumerate(steps) if _get(s, "type") == "user_input"), default=-1)
    items: List[Any] = []
    for step in steps[last_user + 1:]:
        if _get(step, "type") != "model_output":
            continue
        content = _get(step, "content")
        if isinstance(content, str):
            items.append({"type": "text", "text": content})
        else:
            items.extend(content or [])
    return items


def output_text(interaction: Any) -> str:
    """All text produced by the model (joined across model_output steps / long-decode hops)."""
    texts = [_get(i, "text") for i in _model_output_items(interaction) if _get(i, "type") == "text"]
    joined = "".join(t for t in texts if t)
    return joined or (_get(interaction, "output_text") or "")


def output_media(interaction: Any, kind: str) -> Optional[Any]:
    """Last media item of the given kind ('video', 'audio', 'image') the model produced."""
    found = None
    for item in _model_output_items(interaction):
        if _get(item, "type") == kind:
            found = item
    return found or _get(interaction, f"output_{kind}")


def _download_uri(uri: str) -> bytes:
    client = _client()
    match = re.search(r"(files/[A-Za-z0-9_-]+)", uri)
    if match:
        return client.files.download(file=match.group(1))
    import httpx
    from ..core import config
    resp = httpx.get(uri, headers={"x-goog-api-key": config.api_key}, timeout=300, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def media_bytes(item: Any) -> bytes:
    data = _get(item, "data")
    if data:
        return base64.b64decode(data) if isinstance(data, str) else bytes(data)
    uri = _get(item, "uri")
    if uri:
        return _download_uri(uri)
    raise ValueError("media item has neither inline data nor a URI")


def save_media(item: Any, output_path: Optional[str], default_stem: str) -> Tuple[str, int]:
    """Write a media item to disk; fix the extension to match its MIME type. Returns (path, bytes)."""
    mime = _get(item, "mime_type") or ""
    ext = EXT_BY_MIME.get(mime, os.path.splitext(output_path or "")[1] or ".bin")
    if not output_path:
        output_path = f"/tmp/{default_stem}_{int(time.time())}{ext}"
    elif not output_path.lower().endswith(ext):
        output_path = os.path.splitext(output_path)[0] + ext
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    payload = media_bytes(item)
    with open(output_path, "wb") as fh:
        fh.write(payload)
    return output_path, len(payload)


def usage_line(interaction: Any) -> str:
    """Compact token usage summary when the API reports it."""
    usage = _get(interaction, "usage")
    if not usage:
        return ""
    parts = []
    for key, label in (("total_input_tokens", "in"), ("total_output_tokens", "out"),
                       ("total_thought_tokens", "thinking"), ("total_tool_use_tokens", "tools")):
        val = _get(usage, key)
        if val:
            parts.append(f"{label}={val}")
    return " · ".join(parts)
