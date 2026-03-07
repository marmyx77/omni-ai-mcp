"""
FastMCP Server Tests for v4.0.0

Tests:
- Server initialization
- Tool registration (20 tools)
- MCP protocol compliance
"""

import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestFastMCPServerInit:
    """FastMCP server initialization tests."""

    def test_server_imports_successfully(self):
        """Server module imports without errors."""
        from app.server import mcp
        assert mcp is not None

    def test_server_has_correct_name(self):
        """Server has correct name."""
        from app.server import mcp
        assert mcp.name == "omni-ai-mcp"

    def test_server_has_main_function(self):
        """Server has main() entry point."""
        from app.server import main
        assert callable(main)


class TestToolRegistration:
    """Tool registration tests."""

    def test_all_20_tools_registered(self):
        """All 20 tools are registered (v4.0.0)."""
        from app.server import mcp
        tools = list(mcp._tool_manager._tools.keys())
        assert len(tools) == 20

    def test_analysis_tools_registered(self):
        """Analysis tools are registered."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        assert "gemini_analyze_codebase" in tools
        assert "gemini_analyze_image" in tools

    def test_search_tools_registered(self):
        """Search and RAG tools are registered."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        assert "gemini_web_search" in tools
        assert "gemini_file_search" in tools
        assert "gemini_create_file_store" in tools
        assert "gemini_upload_file" in tools
        assert "gemini_list_file_stores" in tools

    def test_generation_tools_registered(self):
        """Generation tools are registered."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        assert "gemini_generate_image" in tools
        assert "gemini_generate_video" in tools
        assert "gemini_text_to_speech" in tools
        assert "gemini_generate_code" in tools

    def test_text_tools_registered(self):
        """Text and reasoning tools are registered."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        assert "ask_gemini" in tools
        assert "gemini_code_review" in tools
        assert "gemini_brainstorm" in tools
        assert "gemini_challenge" in tools

    def test_v4_tools_registered(self):
        """v4.0.0 tools are registered."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        assert "gemini_list_models" in tools
        assert "ask_model" in tools  # Must be ask_model, not ask_model_tool

    def test_conversation_tools_registered(self):
        """Conversation management tools are registered."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        assert "gemini_list_conversations" in tools
        assert "gemini_delete_conversation" in tools

    def test_deep_research_registered(self):
        """Deep research tool is registered."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        assert "gemini_deep_research" in tools

    def test_tool_names_are_strings(self):
        """All tool names are strings."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        for name in tools.keys():
            assert isinstance(name, str)
            assert len(name) > 0


class TestToolMetadata:
    """Tool metadata tests."""

    def test_ask_gemini_has_correct_name(self):
        """ask_gemini tool has explicit name (not _ask_gemini)."""
        from app.server import mcp
        tools = mcp._tool_manager._tools
        assert "ask_gemini" in tools
        assert "_ask_gemini" not in tools

    def test_tools_have_descriptions(self):
        """All tools have descriptions."""
        from app.server import mcp
        for name, tool in mcp._tool_manager._tools.items():
            # FastMCP tools have fn attribute with __doc__
            if hasattr(tool, 'fn') and tool.fn:
                assert tool.fn.__doc__ is not None, f"{name} missing docstring"


class TestMCPResources:
    """MCP resource tests."""

    def test_file_resource_registered(self):
        """File resource is registered."""
        from app.server import mcp
        # Check if resource manager exists
        assert hasattr(mcp, '_resource_manager')


class TestServerEntry:
    """Server entry point tests."""

    def test_run_py_imports_main(self):
        """run.py imports and calls main from app."""
        import sys
        from pathlib import Path

        # Check run.py file exists and imports main
        run_py = Path(__file__).parent.parent.parent / "run.py"
        content = run_py.read_text()

        # run.py imports main from app and calls it
        assert "from app import main" in content or "from app.server import main" in content
        assert "__name__" in content
        assert "main()" in content

    def test_backward_compat_server_imports(self):
        """server.py backward compatibility works."""
        import server
        assert hasattr(server, 'validate_path')
        assert hasattr(server, 'SafeFileWriter')
        assert hasattr(server, 'SANDBOX_ROOT')
        assert hasattr(server, 'SANDBOX_ENABLED')
