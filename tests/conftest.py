"""
Pytest configuration and fixtures for omni-ai-mcp tests.

v2.6.0 Test Suite Foundation
"""

import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_sandbox():
    """Create temporary sandbox directory for tests (sandbox disabled)."""
    from app.core.config import config

    sandbox = tempfile.mkdtemp(prefix="gemini_test_")

    # Save original values from config
    old_sandbox_root = config.sandbox_root
    old_sandbox_enabled = config.sandbox_enabled

    # Patch config (this is what validate_path uses)
    config.sandbox_root = sandbox
    config.sandbox_enabled = False

    yield sandbox

    # Cleanup
    shutil.rmtree(sandbox, ignore_errors=True)
    config.sandbox_root = old_sandbox_root
    config.sandbox_enabled = old_sandbox_enabled


@pytest.fixture
def sandbox_enabled():
    """Create temporary sandbox with sandbox checking enabled."""
    from app.core.config import config

    sandbox = tempfile.mkdtemp(prefix="gemini_test_sandbox_")

    # Save original values from config
    old_sandbox_root = config.sandbox_root
    old_sandbox_enabled = config.sandbox_enabled

    # Patch config - sandbox ENABLED
    config.sandbox_root = sandbox
    config.sandbox_enabled = True

    yield sandbox

    # Cleanup
    shutil.rmtree(sandbox, ignore_errors=True)
    config.sandbox_root = old_sandbox_root
    config.sandbox_enabled = old_sandbox_enabled


@pytest.fixture
def temp_file(temp_sandbox):
    """Create a temporary file within the sandbox."""
    file_path = Path(temp_sandbox) / "test_file.txt"
    file_path.write_text("test content")
    return str(file_path)


@pytest.fixture
def sample_python_file(temp_sandbox):
    """Create a sample Python file for testing."""
    file_path = Path(temp_sandbox) / "sample.py"
    content = '''#!/usr/bin/env python3
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
'''
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def sample_generated_code_xml():
    """Sample XML output for parse_generated_code tests."""
    return '''<GENERATED_CODE>
<FILE action="create" path="src/hello.py">
def hello():
    print("Hello World")
</FILE>
<FILE action="modify" path="src/main.py">
from hello import hello
hello()
</FILE>
</GENERATED_CODE>'''


@pytest.fixture
def sample_need_files_json():
    """Sample JSON for More Info Protocol tests."""
    return '{"need_files": ["src/types.ts", "package.json"]}'


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client for offline testing."""
    with patch('server.client') as mock_client:
        mock_response = Mock()
        mock_response.text = "Mock Gemini response"
        mock_response.candidates = []
        mock_client.models.generate_content.return_value = mock_response
        yield mock_client


@pytest.fixture
def mock_conversation_memory():
    """Mock conversation memory for testing."""
    with patch('server.conversation_memory') as mock_memory:
        mock_thread = Mock()
        mock_thread.is_expired.return_value = False
        mock_thread.can_add_turn.return_value = True
        mock_thread.build_context.return_value = "Previous context"
        mock_memory.get_or_create_thread.return_value = ("test-id", True, mock_thread)
        yield mock_memory


@pytest.fixture
def disable_logging():
    """Disable activity logging for tests."""
    old_value = os.environ.get("GEMINI_ACTIVITY_LOG")
    os.environ["GEMINI_ACTIVITY_LOG"] = "false"
    yield
    if old_value:
        os.environ["GEMINI_ACTIVITY_LOG"] = old_value
    elif "GEMINI_ACTIVITY_LOG" in os.environ:
        del os.environ["GEMINI_ACTIVITY_LOG"]


@pytest.fixture
def test_files_dir(temp_sandbox):
    """Create a directory with various test files."""
    test_dir = Path(temp_sandbox) / "test_files"
    test_dir.mkdir()

    # Create different file types
    (test_dir / "code.py").write_text("print('hello')")
    (test_dir / "data.json").write_text('{"key": "value"}')
    (test_dir / "readme.md").write_text("# README")
    (test_dir / "config.txt").write_text("setting=value")

    # Create nested structure
    (test_dir / "src").mkdir()
    (test_dir / "src" / "main.py").write_text("def main(): pass")
    (test_dir / "src" / "utils.py").write_text("def util(): pass")

    return str(test_dir)
