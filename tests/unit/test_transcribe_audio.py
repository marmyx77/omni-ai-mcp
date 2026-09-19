"""
Unit tests for gemini_transcribe_audio (v4.7.0): config validation, response
parsing into segments, formatting, model category — no API calls.
"""

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.tools.media.transcribe_audio import (  # noqa: E402
    build_transcription_config, parse_transcription, format_transcript, transcribe_audio, AUDIO_MIME_TYPES,
)
from app.services.model_registry import ModelRegistry, CATEGORY_SPECS  # noqa: E402

MOD = sys.modules["app.tools.media.transcribe_audio"]


def _word(w, start, end, speaker=None):
    return SimpleNamespace(word=w, start_offset=f"{start}s", end_offset=f"{end}s", speaker_label=speaker)


def _response(parts):
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))])


def _part(text, speaker=None, words=None, language=None):
    at = SimpleNamespace(text=text, speaker_label=speaker, language_code=language, words=words)
    return SimpleNamespace(audio_transcription=at, text=None)


class TestConfig:
    def test_defaults_to_smart_only(self):
        assert build_transcription_config(False, False, None, None, "smart") == {"mode": "SMART"}
        assert build_transcription_config(False, False, None, None, "auto") == {"mode": "SMART"}

    def test_auto_switches_to_verbatim_with_word_timestamps(self):
        """Live 2026-09-19: the API returns 400 'mode SMART is incompatible with word timestamps'."""
        cfg = build_transcription_config(False, True, None, None, "auto")
        assert cfg == {"mode": "VERBATIM", "word_timestamp": True}

    def test_explicit_smart_with_word_timestamps_is_rejected_locally(self):
        with pytest.raises(ValueError, match="incompatible with word_timestamps"):
            build_transcription_config(False, True, None, None, "smart")

    def test_all_options(self):
        cfg = build_transcription_config(True, True, ["it", " en "], None, "verbatim")
        assert cfg == {"mode": "VERBATIM", "diarization": True, "word_timestamp": True, "language_codes": ["it", "en"]}

    def test_vocabulary_maps_to_custom_vocabulary(self):
        cfg = build_transcription_config(False, False, None, ["MCP", ""], "smart")
        assert cfg["custom_vocabulary"] == ["MCP"]

    def test_diarization_and_vocabulary_are_exclusive(self):
        with pytest.raises(ValueError, match="cannot be combined"):
            build_transcription_config(True, False, None, ["MCP"], "smart")

    def test_unknown_mode_rejected(self):
        with pytest.raises(ValueError, match="mode"):
            build_transcription_config(False, False, None, None, "loud")


class TestParse:
    def test_plain_text_when_response_text_is_empty(self):
        """response.text is empty without options: audio_transcription is the source of truth."""
        r = _response([_part("Ciao a tutti.")])
        result = parse_transcription(r)
        assert result["text"] == "Ciao a tutti."
        assert result["segments"] == [{"speaker": None, "start": None, "end": None, "text": "Ciao a tutti."}]
        assert result["words"] == []

    def test_words_are_grouped_into_sentences_with_timestamps(self):
        words = [_word("Ciao", 0.3, 0.6), _word("a", 0.6, 0.7), _word("tutti.", 0.7, 1.2),
                 _word("Oggi", 1.7, 2.0), _word("parliamo.", 2.0, 2.5)]
        result = parse_transcription(_response([_part("Ciao a tutti. Oggi parliamo.", "spk:0", words)]))
        assert [s["text"] for s in result["segments"]] == ["Ciao a tutti.", "Oggi parliamo."]
        assert result["segments"][0]["start"] == 0.3 and result["segments"][0]["end"] == 1.2
        assert result["segments"][1]["speaker"] == "spk:0"
        assert len(result["words"]) == 5

    def test_speaker_change_splits_a_segment(self):
        words = [_word("Pronto", 0, 0.5, "spk:0"), _word("chi", 0.6, 0.8, "spk:1"), _word("parla?", 0.8, 1.2, "spk:1")]
        result = parse_transcription(_response([_part("Pronto chi parla?", None, words)]))
        assert [(s["speaker"], s["text"]) for s in result["segments"]] == [("spk:0", "Pronto"), ("spk:1", "chi parla?")]

    def test_multiple_parts_and_languages(self):
        r = _response([_part("Hello.", "spk:0", None, "en"), _part("Ciao.", "spk:1", None, "it")])
        result = parse_transcription(r)
        assert result["text"] == "Hello.\nCiao."
        assert result["languages"] == ["en", "it"]


class TestFormat:
    def test_plain_when_no_options(self):
        result = parse_transcription(_response([_part("Ciao a tutti.")]))
        assert format_transcript(result, False, False) == "Ciao a tutti."

    def test_timestamps_and_speakers_prefix_each_sentence(self):
        words = [_word("Ciao", 65.3, 65.6, "spk:0"), _word("tutti.", 65.6, 66.0, "spk:0")]
        result = parse_transcription(_response([_part("Ciao tutti.", None, words)]))
        assert format_transcript(result, True, True) == "[01:05.3] spk:0: Ciao tutti."
        assert format_transcript(result, False, True) == "[01:05.3] Ciao tutti."
        assert format_transcript(result, True, False) == "spk:0: Ciao tutti."


class TestTool:
    @pytest.fixture
    def fake(self, monkeypatch, tmp_path):
        calls = {}

        class Models:
            def generate_content(self, model, contents, config):
                calls["model"] = model
                calls["config"] = config
                return _response([_part("Buongiorno a tutti.", None, None, "it")])

        monkeypatch.setattr(MOD, "client", SimpleNamespace(models=Models(), files=None))
        monkeypatch.setattr(MOD, "is_available", lambda: True)
        monkeypatch.setattr(MOD, "resolve_model", lambda: "gemini-3.5-transcribe")
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....WAVEfmt ")
        return calls, audio, tmp_path

    def test_missing_file(self, fake):
        assert transcribe_audio("/nope/x.wav").startswith("Error: audio file not found")

    def test_unsupported_format(self, fake, tmp_path):
        bad = tmp_path / "a.txt"; bad.write_text("x")
        out = transcribe_audio(str(bad))
        assert out.startswith("Error: unsupported audio format")
        assert ".wav" in out

    def test_happy_path_header_and_text(self, fake):
        calls, audio, _ = fake
        out = transcribe_audio(str(audio), language_codes=["it"])
        assert out.startswith("[Transcribed with gemini-3.5-transcribe · mode=smart · language=it]")
        assert "Buongiorno a tutti." in out
        assert calls["model"] == "gemini-3.5-transcribe"
        assert calls["config"].audio_transcription_config.language_codes == ["it"]

    def test_invalid_combination_is_reported_not_raised(self, fake):
        _, audio, _ = fake
        assert "cannot be combined" in transcribe_audio(str(audio), diarization=True, vocabulary=["x"])

    def test_output_path_json_and_txt(self, fake):
        _, audio, tmp = fake
        out = transcribe_audio(str(audio), output_path=str(tmp / "t.json"))
        data = json.loads((tmp / "t.json").read_text())
        assert data["model"] == "gemini-3.5-transcribe" and data["text"] == "Buongiorno a tutti."
        assert "Saved to:" in out
        transcribe_audio(str(audio), output_path=str(tmp / "t.txt"))
        assert (tmp / "t.txt").read_text().strip() == "Buongiorno a tutti."

    def test_every_supported_extension_has_a_mime(self):
        assert all(v.startswith("audio/") for v in AUDIO_MIME_TYPES.values())


class TestRegistryCategory:
    def test_transcribe_category_picks_newest_and_ignores_live(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL_TRANSCRIBE", raising=False)
        reg = ModelRegistry()
        reg._available_model_names = ["gemini-3.5-transcribe", "gemini-3.5-transcribe-live", "gemini-3.8-transcribe"]
        reg._cache_timestamp = time.time()
        assert reg.resolve("transcribe") == "gemini-3.8-transcribe"
        assert CATEGORY_SPECS["transcribe"].version_key("gemini-3.5-transcribe-live") is None
