"""
Unit tests for the v4.8.0 media tools: video (Omni Flash), TTS 3.8, music
(Lyria), video understanding, voices. Requests are validated against the
official SDK request schema when the SDK exposes it. No network.
"""

import base64
import io
import json
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import app.tools.media.generate_video  # noqa: E402,F401
import app.tools.media.text_to_speech  # noqa: E402,F401
import app.tools.media.generate_music  # noqa: E402,F401
import app.tools.media.analyze_video  # noqa: E402,F401
import app.tools.media.voices  # noqa: E402,F401
from app.services import interactions as ix  # noqa: E402

VIDEO = sys.modules["app.tools.media.generate_video"]
TTS = sys.modules["app.tools.media.text_to_speech"]
MUSIC = sys.modules["app.tools.media.generate_music"]
AVIDEO = sys.modules["app.tools.media.analyze_video"]
VOICES = sys.modules["app.tools.media.voices"]

try:  # official request schema (google-genai >= 2.33)
    from google.genai._gaos.google_genai import interactions as SDK_I
except Exception:  # pragma: no cover - older SDK
    SDK_I = None


def assert_valid_model_request(req):
    if SDK_I is None:
        pytest.skip("SDK request schema not available")
    SDK_I.CreateModelInteraction.model_validate(req)


def completed(*items, iid="v1_done", model=None):
    return {"id": iid, "status": "completed", "model": model,
            "steps": [{"type": "user_input", "content": [{"type": "text", "text": "q"}]},
                      {"type": "model_output", "content": list(items)}]}


@pytest.fixture
def no_api(monkeypatch):
    for mod in (VIDEO, TTS, MUSIC, AVIDEO, VOICES):
        monkeypatch.setattr(mod, "is_available", lambda: True)
    monkeypatch.setattr(ix, "cleanup", lambda names: None)


# ------------------------------------------------------------------ video

class TestVideo:
    def test_request_shapes_are_valid_for_the_sdk(self):
        img = {"type": "image", "data": "aGk=", "mime_type": "image/png"}
        for req in (
            VIDEO.build_video_request("gemini-omni-1.1-flash", "a cat", [], None, "auto", "16:9", "720p", None, None, None),
            VIDEO.build_video_request("gemini-omni-1.1-flash", "<FIRST_FRAME> <LAST_FRAME> x", [img, img], None,
                                      "image_to_video", "9:16", "4k", 8, "blur", None),
            VIDEO.build_video_request("gemini-omni-1.1-flash", "Make it anime.", [], None, "edit", "16:9", "720p", None, None, "v1_prev"),
        ):
            assert_valid_model_request(req)

    def test_high_resolutions_use_uri_delivery_and_duration_is_seconds(self):
        req = VIDEO.build_video_request("m", "x", [], None, "auto", "16:9", "1080p", 6, None, None)
        assert req["response_format"]["delivery"] == "uri" and req["response_format"]["duration"] == "6s"
        assert req["background"] is True

    def test_negative_prompt_is_appended(self):
        req = VIDEO.build_video_request("m", "a beach", [], None, "auto", "16:9", "720p", None, "people, text", None)
        assert req["input"] == "a beach\nAvoid: people, text"

    @pytest.mark.parametrize("kwargs, match", [
        (dict(aspect_ratio="1:1"), "aspect_ratio"), (dict(resolution="8k"), "resolution"),
        (dict(duration=12), "duration"), (dict(task="morph"), "task"),
    ])
    def test_invalid_arguments(self, kwargs, match):
        args = dict(model_id="m", prompt="x", image_blocks=[], video_block=None, task="auto", aspect_ratio="16:9",
                    resolution="720p", duration=None, negative_prompt=None, continuation_id=None)
        args.update(kwargs)
        with pytest.raises(ValueError, match=match):
            VIDEO.build_video_request(**args)

    def test_tool_saves_video_and_returns_continuation_id(self, no_api, monkeypatch, tmp_path):
        item = {"type": "video", "data": base64.b64encode(b"mp4").decode(), "mime_type": "video/mp4"}
        sent = {}
        monkeypatch.setattr(ix, "run", lambda req, t, p=5: sent.update(req) or completed(item, iid="v1_vid", model="gemini-omni-1.1-flash"))
        monkeypatch.setattr(VIDEO, "VIDEO_MODELS", {"omni": "gemini-omni-1.1-flash"})
        out = VIDEO.generate_video("a cat", output_path=str(tmp_path / "cat"), model="veo31")
        assert (tmp_path / "cat.mp4").read_bytes() == b"mp4"
        assert "continuation_id: v1_vid" in out and "shut down upstream" in out
        assert sent["model"] == "gemini-omni-1.1-flash"

    def test_timeout_explains_how_to_retrieve(self, no_api, monkeypatch):
        def boom(req, t, p=5):
            raise ix.InteractionTimeout("v1_slow", 600)
        monkeypatch.setattr(ix, "run", boom)
        monkeypatch.setattr(VIDEO, "VIDEO_MODELS", {"omni": "m"})
        assert "retrieve_id='v1_slow'" in VIDEO.generate_video("x")

    def test_retrieve_id_waits_and_saves(self, no_api, monkeypatch, tmp_path):
        item = {"type": "video", "data": base64.b64encode(b"late").decode(), "mime_type": "video/mp4"}
        monkeypatch.setattr(ix, "wait", lambda iid, t, p=5: completed(item, iid=iid))
        out = VIDEO.generate_video("ignored", retrieve_id="v1_late", output_path=str(tmp_path / "late.mp4"))
        assert (tmp_path / "late.mp4").read_bytes() == b"late" and "v1_late" in out

    def test_non_video_source_is_rejected(self, no_api, tmp_path):
        f = tmp_path / "a.png"; f.write_bytes(b"x")
        assert "is not a video file" in VIDEO.generate_video("x", video_path=str(f))


# -------------------------------------------------------------------- TTS

def _wav(seconds=1.0, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


class TestTTS:
    def test_single_voice_request_with_style_and_language(self):
        req = TTS.build_tts_request("gemini-3.8-flash-tts", "Ciao a tutti", "Kore", "warm", "it-IT", None)
        assert req["generation_config"]["speech_config"] == [{"voice": "Kore", "language": "it-IT"}]
        assert req["input"][0]["content"][0]["annotations"] == [{"type": "speech_metadata", "style": "warm"}]
        assert_valid_model_request(req)

    def test_dialogue_request_turns_and_speakers(self):
        speakers = [{"name": "Joe", "voice": "Puck", "style": "cheerful"}, {"name": "Jane", "voice": "voice_abc"}]
        req = TTS.build_tts_request("m", "Joe: Ciao Jane\nJane: Ciao Joe,\ncome stai?", "Kore", None, None, speakers)
        content = req["input"][0]["content"]
        assert [c["text"] for c in content] == ["Ciao Jane", "Ciao Joe, come stai?"]
        assert content[0]["annotations"][0] == {"type": "speech_metadata", "speaker": "Joe", "style": "cheerful"}
        assert req["generation_config"]["speech_config"] == {"speakers": [{"speaker": "Joe", "voice": "Puck"}, {"speaker": "Jane", "voice": "voice_abc"}]}
        assert_valid_model_request({**req, "model": "gemini-3.8-flash-tts"})

    def test_dialogue_without_named_lines_is_an_error(self):
        with pytest.raises(ValueError, match="no dialogue lines"):
            TTS.build_tts_request("m", "just text", "Kore", None, None, [{"name": "A", "voice": "Puck"}, {"name": "B", "voice": "Kore"}])

    def test_pcm_is_wrapped_into_wav_and_wav_passes_through(self):
        wav = TTS.wav_bytes(b"\x00\x00" * 24000, "audio/l16", 24000)
        assert wav[:4] == b"RIFF" and abs(TTS.wav_duration(wav) - 1.0) < 0.01
        original = _wav(0.5)
        assert TTS.wav_bytes(original, "audio/wav", None) is original

    def test_tool_saves_wav_with_duration(self, no_api, monkeypatch, tmp_path):
        item = {"type": "audio", "data": base64.b64encode(_wav(2.0)).decode(), "mime_type": "audio/wav"}
        monkeypatch.setattr(ix, "run", lambda req, t, p=5: completed(item))
        monkeypatch.setattr(TTS, "TTS_MODELS", {"flash": "gemini-3.8-flash-tts", "lite": "x", "pro": "gemini-3.8-flash-tts"})
        out = TTS.text_to_speech("Ciao", voice="voice_custom", output_path=str(tmp_path / "a.mp3"), style="calm")
        assert (tmp_path / "a.wav").exists() and "Duration: 2.0s" in out and "voice_custom" in out


# ------------------------------------------------------------------ music

class TestMusic:
    def test_request_text_and_images(self):
        assert MUSIC.build_music_request("lyria-3.5", " a song ", []) == {"model": "lyria-3.5", "input": "a song", "background": True}
        img = {"type": "image", "data": "aGk=", "mime_type": "image/png"}
        req = MUSIC.build_music_request("lyria-3.5", "inspired by this", [img])
        assert req["input"][-1] == {"type": "text", "text": "inspired by this"}
        assert_valid_model_request(req)

    def test_tool_saves_mp3_and_returns_lyrics(self, no_api, monkeypatch, tmp_path):
        audio = {"type": "audio", "data": base64.b64encode(b"ID3").decode(), "mime_type": "audio/mp3"}
        monkeypatch.setattr(ix, "run", lambda req, t, p=5: completed(audio, {"type": "text", "text": "[Verse] la la"}))
        monkeypatch.setattr(MUSIC, "MUSIC_MODELS", {"full": "lyria-3.5", "clip": "lyria-3-clip-preview"})
        out = MUSIC.generate_music("pop song", output_path=str(tmp_path / "s"))
        assert (tmp_path / "s.mp3").read_bytes() == b"ID3" and "[Verse] la la" in out

    def test_timeout_offers_retrieval(self, no_api, monkeypatch):
        def boom(req, t, p=5):
            raise ix.InteractionTimeout("v1_song", 600)
        monkeypatch.setattr(ix, "run", boom)
        monkeypatch.setattr(MUSIC, "MUSIC_MODELS", {"full": "m", "clip": "c"})
        assert "retrieve_id='v1_song'" in MUSIC.generate_music("x")


# ------------------------------------------------------- video analysis

class TestAnalyzeVideo:
    def test_youtube_block_with_agentic_processing(self):
        block, name = AVIDEO.video_block_for(None, "https://www.youtube.com/watch?v=abc", "agentic", "high")
        assert block == {"type": "video", "uri": "https://www.youtube.com/watch?v=abc", "processing": "agentic", "resolution": "high"}
        assert name is None
        assert_valid_model_request(AVIDEO.build_video_analysis_request("gemini-3.8-flash", block, "summarize"))

    @pytest.mark.parametrize("path, url, match", [
        (None, None, "exactly one"), ("a.mp4", "https://youtu.be/x", "exactly one"),
        (None, "https://vimeo.com/1", "youtube"),
    ])
    def test_source_validation(self, path, url, match):
        with pytest.raises(ValueError, match=match):
            AVIDEO.video_block_for(path, url, "static", None)

    def test_agentic_requires_a_supporting_model(self, no_api, monkeypatch):
        monkeypatch.setattr(AVIDEO, "MODELS", {"flash": "gemini-3.8-flash", "robotics": "gemini-robotics-er-2-preview"})
        out = AVIDEO.analyze_video("x", youtube_url="https://youtu.be/abc", processing="agentic", model="robotics")
        assert out.startswith("Error: agentic processing is not supported")

    @pytest.mark.parametrize("model_id, ok", [("gemini-4-argon", True), ("gemini-3.8-flash", True),
                                              ("gemini-3.6-flash", True), ("gemini-3.5-flash-lite", True),
                                              ("gemini-3.1-pro-preview", False), ("gemini-3.5-flash", False)])
    def test_agentic_family_matcher(self, model_id, ok):
        assert bool(AVIDEO.AGENTIC_FAMILIES.match(model_id)) is ok

    def test_tool_returns_text_and_footer(self, no_api, monkeypatch):
        monkeypatch.setattr(AVIDEO, "MODELS", {"flash": "gemini-3.8-flash"})
        monkeypatch.setattr(ix, "run", lambda req, t, p=5: completed({"type": "text", "text": "At 01:23 the speaker..."}))
        out = AVIDEO.analyze_video("key moments", youtube_url="https://youtu.be/abc", processing="agentic")
        assert "01:23" in out and "agentic processing" in out


# ----------------------------------------------------------------- voices

class FakeVoices:
    def __init__(self):
        self.calls = []

    def list(self, **kw):
        self.calls.append(("list", kw))
        return {"voices": [{"id": "it-voice-1", "display_name": "Giulia", "language_code": "it-IT", "gender": "female",
                            "pitch": "medium", "description": "Warm narrator"}], "next_page_token": "p2"}

    def create(self, **kw):
        self.calls.append(("create", kw))
        sample = {"data": base64.b64encode(_wav(0.2)).decode()}
        return {"id": "voice_xyz", "key": "voicekey_abc", "sample_audio": sample}


@pytest.fixture
def fake_voices(no_api, monkeypatch):
    fv = FakeVoices()
    monkeypatch.setattr(VOICES, "_voices_api", lambda: fv)
    monkeypatch.setattr(VOICES, "TTS_MODELS", {"flash": "gemini-3.8-flash-tts", "lite": "gemini-3.8-flash-lite-tts"})
    return fv


class TestVoices:
    def test_list_filters_map_to_sdk_names(self):
        f = VOICES.build_list_filters(["it-IT"], ["female"], None, None, None, "Audiobook,News", ["prebuilt"], "warm", 5000)
        assert f == {"language_code": ["it-IT"], "gender": ["female"], "contexts": ["Audiobook", "News"],
                     "type_": ["prebuilt"], "search": "warm", "page_size": 1000}

    def test_invalid_filter_values(self):
        with pytest.raises(ValueError, match="gender"):
            VOICES.build_list_filters(gender=["robot"])

    def test_list_tool_formats_and_paginates(self, fake_voices):
        out = VOICES.list_voices(language_codes=["it-IT"])
        assert "`it-voice-1` Giulia (it-IT, female, pitch=medium): Warm narrator" in out and "page_token='p2'" in out

    def test_design_voice_request_and_preview(self, fake_voices, tmp_path):
        out = VOICES.design_voice("A calm Italian radio host in her 40s", gender="female", language_code="it-IT",
                                  preview_path=str(tmp_path / "p.wav"))
        kind, kw = fake_voices.calls[-1]
        assert kw == {"store": True, "voice": {"model": "gemini-3.8-flash-tts", "type": "prompted", "display_name": "Custom voice",
                                               "prompted": {"input": "A calm Italian radio host in her 40s"},
                                               "gender": "female", "language_code": "it-IT"}}
        assert "voice_xyz" in out and (tmp_path / "p.wav").exists()

    def test_design_needs_a_real_description(self):
        with pytest.raises(ValueError):
            VOICES.build_design_request("m", "short", "x", None, None)

    def test_replication_checks_files_and_reference_length(self, tmp_path):
        short = tmp_path / "short.wav"; short.write_bytes(_wav(3))
        consent = tmp_path / "consent.wav"; consent.write_bytes(_wav(6))
        with pytest.raises(ValueError, match="10-30 s"):
            VOICES.build_replication_request("m", str(short), str(consent), "x", True)
        mp3 = tmp_path / "a.mp3"; mp3.write_bytes(b"x")
        with pytest.raises(ValueError, match="WAV"):
            VOICES.build_replication_request("m", str(mp3), str(consent), "x", True)

    def test_replication_stateless_returns_key(self, fake_voices, tmp_path):
        ref = tmp_path / "ref.wav"; ref.write_bytes(_wav(12))
        consent = tmp_path / "consent.wav"; consent.write_bytes(_wav(6))
        out = VOICES.replicate_voice(str(ref), str(consent), store=False)
        kind, kw = fake_voices.calls[-1]
        assert kw["store"] is False and kw["voice"]["type"] == "replicated"
        assert set(kw["voice"]["replicated"]) == {"source_audio", "consent_audio"}
        assert "voicekey_abc" in out
