"""
Unit tests for app.services.interactions (v4.8.0): file inputs, polling,
output extraction from the 'steps' schema, media saving. No network.
"""

import base64
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import interactions as ix  # noqa: E402


def step(type_, *items):
    return {"type": type_, "content": list(items)}


def text(t):
    return {"type": "text", "text": t}


class FakeInteractions:
    def __init__(self, created_status="completed", polls=None):
        self.created_status = created_status
        self.polls = list(polls or [])
        self.created = []
        self.got = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return {"id": "v1_new", "status": self.created_status,
                "steps": [step("user_input", text("hi")), step("model_output", text("done"))]}

    def get(self, interaction_id):
        self.got.append(interaction_id)
        return self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]


@pytest.fixture
def fake_client(monkeypatch):
    holder = SimpleNamespace(interactions=FakeInteractions(), files=SimpleNamespace())
    monkeypatch.setattr(ix, "_client", lambda: holder)
    monkeypatch.setattr(ix.time, "sleep", lambda s: None)
    return holder


class TestOutputs:
    def test_text_joins_every_model_output_after_the_last_user_input(self):
        interaction = {"steps": [
            step("user_input", text("old question")), step("model_output", text("old answer")),
            step("user_input", text("new question")), step("thought", text("thinking...")),
            step("model_output", text("part 1 ")), step("tool_call"), step("model_output", text("part 2")),
        ]}
        assert ix.output_text(interaction) == "part 1 part 2"

    def test_media_is_the_last_item_of_its_kind(self):
        v1 = {"type": "video", "data": "AA==", "mime_type": "video/mp4"}
        v2 = {"type": "video", "uri": "https://x/files/abc", "mime_type": "video/mp4"}
        interaction = {"steps": [step("user_input", text("q")), step("model_output", v1, text("caption"), v2)]}
        assert ix.output_media(interaction, "video") is v2
        assert ix.output_media(interaction, "audio") is None

    def test_falls_back_to_sdk_convenience_properties(self):
        obj = SimpleNamespace(steps=[], output_text="from sdk", output_audio={"type": "audio"})
        assert ix.output_text(obj) == "from sdk"
        assert ix.output_media(obj, "audio") == {"type": "audio"}


class TestSaveMedia:
    def test_inline_data_and_extension_fix(self, tmp_path):
        item = {"type": "audio", "data": base64.b64encode(b"ID3fake").decode(), "mime_type": "audio/mp3"}
        path, size = ix.save_media(item, str(tmp_path / "song.wav"), "x")
        assert path.endswith("song.mp3") and size == 7
        assert Path(path).read_bytes() == b"ID3fake"

    def test_uri_delivery_downloads_through_files_api(self, tmp_path, fake_client):
        fake_client.files.download = lambda file: b"mp4bytes" if file == "files/abc123" else b""
        item = {"type": "video", "uri": "https://generativelanguage.googleapis.com/v1beta/files/abc123:download", "mime_type": "video/mp4"}
        path, size = ix.save_media(item, str(tmp_path / "out"), "x")
        assert path.endswith("out.mp4") and Path(path).read_bytes() == b"mp4bytes"

    def test_item_without_data_or_uri_raises(self):
        with pytest.raises(ValueError):
            ix.media_bytes({"type": "video"})


class TestFileBlock:
    def test_small_file_is_inline(self, tmp_path):
        f = tmp_path / "a.png"; f.write_bytes(b"\x89PNG....")
        block, name = ix.file_block(str(f), resolution="high")
        assert block["type"] == "image" and block["mime_type"] == "image/png" and block["resolution"] == "high"
        assert base64.b64decode(block["data"]) == b"\x89PNG...." and name is None

    def test_forced_upload_uses_files_api(self, tmp_path, fake_client):
        f = tmp_path / "clip.mp4"; f.write_bytes(b"0" * 10)
        uploaded = SimpleNamespace(name="files/1", uri="https://g/files/1", mime_type="video/mp4", state=SimpleNamespace(name="ACTIVE"))
        fake_client.files.upload = lambda file, config: uploaded
        block, name = ix.file_block(str(f), force_upload=True, processing="agentic")
        assert block == {"type": "video", "uri": "https://g/files/1", "mime_type": "video/mp4", "processing": "agentic"}
        assert name == "files/1"

    def test_unknown_extension_is_rejected(self, tmp_path):
        f = tmp_path / "a.xyz"; f.write_text("x")
        with pytest.raises(ValueError, match="unsupported file type"):
            ix.file_block(str(f))


class TestRun:
    def test_synchronous_completion_returns_immediately(self, fake_client):
        out = ix.run({"model": "m", "input": "hi"}, timeout_seconds=10)
        assert ix.output_text(out) == "done" and fake_client.interactions.got == []

    def test_background_run_is_polled_until_completed(self, fake_client):
        fake_client.interactions.created_status = "in_progress"
        fake_client.interactions.polls = [{"id": "v1_new", "status": "in_progress"},
                                          {"id": "v1_new", "status": "completed", "steps": [step("model_output", text("ok"))]}]
        out = ix.run({"model": "m", "input": "hi", "background": True}, timeout_seconds=60)
        assert ix.output_text(out) == "ok"

    def test_failure_raises_with_detail(self, fake_client):
        fake_client.interactions.created_status = "in_progress"
        fake_client.interactions.polls = [{"id": "v1_new", "status": "failed", "error": "safety block"}]
        with pytest.raises(ix.InteractionFailed, match="safety block"):
            ix.run({"model": "m"}, timeout_seconds=60)

    def test_timeout_carries_the_interaction_id(self, fake_client, monkeypatch):
        fake_client.interactions.created_status = "in_progress"
        fake_client.interactions.polls = [{"id": "v1_new", "status": "in_progress"}]
        clock = iter([0, 0, 1000, 1000, 1000])
        monkeypatch.setattr(ix.time, "time", lambda: next(clock))
        with pytest.raises(ix.InteractionTimeout) as err:
            ix.run({"model": "m"}, timeout_seconds=60)
        assert err.value.interaction_id == "v1_new"
