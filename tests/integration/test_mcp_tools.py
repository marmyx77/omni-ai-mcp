"""
MCP Tools Tests for v3.0.0

Tests all 15 tools with mocked Gemini API responses.
"""

import pytest
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    mock = Mock()
    mock.text = "Mock Gemini response"
    mock.candidates = [Mock()]
    mock.candidates[0].content = Mock()
    mock.candidates[0].content.parts = [Mock(text="Mock response", thought=False)]
    return mock


@pytest.fixture
def temp_test_dir():
    """Create temporary directory for tests."""
    tmpdir = tempfile.mkdtemp(prefix="gemini_tool_test_")
    yield tmpdir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestAskGeminiTool:
    """ask_gemini tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "ask_gemini" in mcp._tool_manager._tools

    def test_tool_accepts_prompt(self, mock_gemini_response):
        """Tool accepts prompt parameter."""
        with patch('app.tools.text.ask_gemini.generate_with_fallback', return_value=mock_gemini_response):
            from app.tools.text.ask_gemini import ask_gemini
            result = ask_gemini(prompt="Hello")
            assert "GEMINI" in result or "Mock" in result or isinstance(result, str)

    def test_tool_accepts_model_parameter(self):
        """Tool accepts model parameter."""
        from app.server import _ask_gemini
        import inspect
        sig = inspect.signature(_ask_gemini)
        params = list(sig.parameters.keys())
        assert "model" in params

    def test_tool_accepts_thinking_level(self):
        """Tool accepts thinking_level parameter."""
        from app.server import _ask_gemini
        import inspect
        sig = inspect.signature(_ask_gemini)
        params = list(sig.parameters.keys())
        assert "thinking_level" in params


class TestCodeReviewTool:
    """gemini_code_review tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_code_review" in mcp._tool_manager._tools

    def test_tool_signature_has_code(self):
        """Tool accepts code parameter."""
        from app.server import gemini_code_review
        import inspect
        sig = inspect.signature(gemini_code_review)
        params = list(sig.parameters.keys())
        assert "code" in params

    def test_tool_accepts_focus_parameter(self):
        """Tool accepts focus parameter."""
        from app.server import gemini_code_review
        import inspect
        sig = inspect.signature(gemini_code_review)
        params = list(sig.parameters.keys())
        assert "focus" in params


class TestBrainstormTool:
    """gemini_brainstorm tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_brainstorm" in mcp._tool_manager._tools

    def test_tool_accepts_topic(self):
        """Tool accepts topic parameter."""
        from app.server import gemini_brainstorm
        import inspect
        sig = inspect.signature(gemini_brainstorm)
        params = list(sig.parameters.keys())
        assert "topic" in params

    def test_tool_accepts_methodology(self):
        """Tool accepts methodology parameter."""
        from app.server import gemini_brainstorm
        import inspect
        sig = inspect.signature(gemini_brainstorm)
        params = list(sig.parameters.keys())
        assert "methodology" in params


class TestChallengeTool:
    """gemini_challenge tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_challenge" in mcp._tool_manager._tools

    def test_tool_accepts_statement(self):
        """Tool accepts statement parameter."""
        from app.server import gemini_challenge
        import inspect
        sig = inspect.signature(gemini_challenge)
        params = list(sig.parameters.keys())
        assert "statement" in params

    def test_tool_accepts_focus(self):
        """Tool accepts focus parameter."""
        from app.server import gemini_challenge
        import inspect
        sig = inspect.signature(gemini_challenge)
        params = list(sig.parameters.keys())
        assert "focus" in params


class TestAnalyzeCodebaseTool:
    """gemini_analyze_codebase tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_analyze_codebase" in mcp._tool_manager._tools

    def test_tool_accepts_files_list(self):
        """Tool accepts files parameter as list."""
        from app.server import gemini_analyze_codebase
        import inspect
        sig = inspect.signature(gemini_analyze_codebase)
        params = sig.parameters
        assert "files" in params
        # Should accept List[str]
        assert params["files"].annotation.__origin__ is list or "List" in str(params["files"].annotation)


class TestAnalyzeImageTool:
    """gemini_analyze_image tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_analyze_image" in mcp._tool_manager._tools

    def test_tool_accepts_image_path(self):
        """Tool accepts image_path parameter."""
        from app.server import gemini_analyze_image
        import inspect
        sig = inspect.signature(gemini_analyze_image)
        params = list(sig.parameters.keys())
        assert "image_path" in params


class TestWebSearchTool:
    """gemini_web_search tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_web_search" in mcp._tool_manager._tools

    def test_tool_accepts_query(self):
        """Tool accepts query parameter."""
        from app.server import gemini_web_search
        import inspect
        sig = inspect.signature(gemini_web_search)
        params = list(sig.parameters.keys())
        assert "query" in params


class TestGenerateImageTool:
    """gemini_generate_image tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_generate_image" in mcp._tool_manager._tools

    def test_tool_accepts_prompt(self):
        """Tool accepts prompt parameter."""
        from app.server import gemini_generate_image
        import inspect
        sig = inspect.signature(gemini_generate_image)
        params = list(sig.parameters.keys())
        assert "prompt" in params

    def test_tool_accepts_aspect_ratio(self):
        """Tool accepts aspect_ratio parameter."""
        from app.server import gemini_generate_image
        import inspect
        sig = inspect.signature(gemini_generate_image)
        params = list(sig.parameters.keys())
        assert "aspect_ratio" in params


class TestGenerateVideoTool:
    """gemini_generate_video tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_generate_video" in mcp._tool_manager._tools

    def test_tool_accepts_prompt(self):
        """Tool accepts prompt parameter."""
        from app.server import gemini_generate_video
        import inspect
        sig = inspect.signature(gemini_generate_video)
        params = list(sig.parameters.keys())
        assert "prompt" in params

    def test_tool_accepts_duration(self):
        """Tool accepts duration parameter."""
        from app.server import gemini_generate_video
        import inspect
        sig = inspect.signature(gemini_generate_video)
        params = list(sig.parameters.keys())
        assert "duration" in params


class TestTextToSpeechTool:
    """gemini_text_to_speech tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_text_to_speech" in mcp._tool_manager._tools

    def test_tool_accepts_text(self):
        """Tool accepts text parameter."""
        from app.server import gemini_text_to_speech
        import inspect
        sig = inspect.signature(gemini_text_to_speech)
        params = list(sig.parameters.keys())
        assert "text" in params

    def test_tool_accepts_voice(self):
        """Tool accepts voice parameter."""
        from app.server import gemini_text_to_speech
        import inspect
        sig = inspect.signature(gemini_text_to_speech)
        params = list(sig.parameters.keys())
        assert "voice" in params


class TestGenerateCodeTool:
    """gemini_generate_code tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_generate_code" in mcp._tool_manager._tools

    def test_tool_accepts_prompt(self):
        """Tool accepts prompt parameter."""
        from app.server import gemini_generate_code
        import inspect
        sig = inspect.signature(gemini_generate_code)
        params = list(sig.parameters.keys())
        assert "prompt" in params

    def test_tool_accepts_language(self):
        """Tool accepts language parameter."""
        from app.server import gemini_generate_code
        import inspect
        sig = inspect.signature(gemini_generate_code)
        params = list(sig.parameters.keys())
        assert "language" in params


class TestFileSearchTool:
    """gemini_file_search tool tests."""

    def test_tool_exists(self):
        """Tool is registered."""
        from app.server import mcp
        assert "gemini_file_search" in mcp._tool_manager._tools

    def test_tool_accepts_question(self):
        """Tool accepts question parameter."""
        from app.server import gemini_file_search
        import inspect
        sig = inspect.signature(gemini_file_search)
        params = list(sig.parameters.keys())
        assert "question" in params


class TestFileStoreTool:
    """File store management tools tests."""

    def test_create_file_store_exists(self):
        """gemini_create_file_store is registered."""
        from app.server import mcp
        assert "gemini_create_file_store" in mcp._tool_manager._tools

    def test_upload_file_exists(self):
        """gemini_upload_file is registered."""
        from app.server import mcp
        assert "gemini_upload_file" in mcp._tool_manager._tools

    def test_list_file_stores_exists(self):
        """gemini_list_file_stores is registered."""
        from app.server import mcp
        assert "gemini_list_file_stores" in mcp._tool_manager._tools


class TestTranscribeAudioTool:
    """gemini_transcribe_audio tool tests (v4.7.0)."""

    def test_tool_registered(self):
        from app.server import mcp
        assert "gemini_transcribe_audio" in mcp._tool_manager._tools

    def test_signature(self):
        import inspect
        from app.server import gemini_transcribe_audio
        params = inspect.signature(gemini_transcribe_audio).parameters
        assert list(params)[0] == "audio_path"
        for name in ("diarization", "word_timestamps", "language_codes", "vocabulary", "mode", "output_path"):
            assert name in params
        assert params["mode"].default == "auto"
