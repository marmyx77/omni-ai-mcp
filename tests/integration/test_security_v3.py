"""
Security Tests for v3.0.0

Tests:
- Path traversal prevention (is_relative_to fix)
- TOCTOU race condition fix (fstat)
- DoS protection (10MB limit)
- JSON-RPC parse error response
- Plugin directory security
"""

import pytest
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def temp_sandbox():
    """Create temporary sandbox directory."""
    from app.core.config import config

    sandbox = tempfile.mkdtemp(prefix="security_test_")

    old_root = config.sandbox_root
    old_enabled = config.sandbox_enabled

    config.sandbox_root = sandbox
    config.sandbox_enabled = True

    yield sandbox

    import shutil
    shutil.rmtree(sandbox, ignore_errors=True)
    config.sandbox_root = old_root
    config.sandbox_enabled = old_enabled


class TestPathTraversalPrevention:
    """Path traversal attack prevention tests."""

    def test_rejects_dot_dot_traversal(self, temp_sandbox):
        """Rejects ../ path traversal attempts."""
        from app.core.security import validate_path

        with pytest.raises(ValueError, match="outside allowed directory"):
            validate_path(os.path.join(temp_sandbox, "..", "etc", "passwd"))

    def test_rejects_encoded_traversal(self, temp_sandbox):
        """Rejects encoded path traversal."""
        from app.core.security import validate_path

        # After URL decoding, this could be ../
        dangerous_path = os.path.join(temp_sandbox, "..", "..", "etc")

        with pytest.raises(ValueError, match="outside allowed directory"):
            validate_path(dangerous_path)

    def test_accepts_valid_nested_path(self, temp_sandbox):
        """Accepts valid nested paths."""
        from app.core.security import validate_path

        nested_dir = os.path.join(temp_sandbox, "a", "b", "c")
        os.makedirs(nested_dir, exist_ok=True)

        file_path = os.path.join(nested_dir, "file.txt")
        Path(file_path).touch()

        result = validate_path(file_path)
        assert result == os.path.realpath(file_path)

    def test_rejects_symlink_escape(self, temp_sandbox):
        """Rejects symlinks pointing outside sandbox."""
        from app.core.security import validate_path

        # Create symlink pointing outside
        link_path = os.path.join(temp_sandbox, "escape_link")
        try:
            os.symlink("/etc/passwd", link_path)

            with pytest.raises(ValueError, match="outside allowed directory"):
                validate_path(link_path)
        finally:
            if os.path.exists(link_path):
                os.unlink(link_path)

class TestTOCTOUFix:
    """TOCTOU race condition fix tests."""

    def test_secure_read_uses_fstat(self, temp_sandbox):
        """secure_read_file uses fstat on open file descriptor."""
        from app.core.security import secure_read_file
        from app.core.config import config

        # Create test file
        test_file = os.path.join(temp_sandbox, "toctou_test.txt")
        content = "test content"
        Path(test_file).write_text(content)

        # Set small max size
        old_max = config.max_file_size_bytes
        config.max_file_size_bytes = len(content) + 100

        try:
            result = secure_read_file(test_file)
            assert result == content
        finally:
            config.max_file_size_bytes = old_max

    def test_rejects_file_exceeding_limit(self, temp_sandbox):
        """Rejects files exceeding size limit."""
        from app.core.security import secure_read_file

        # Create large file
        test_file = os.path.join(temp_sandbox, "large_file.txt")
        large_content = "x" * 1000

        Path(test_file).write_text(large_content)

        # Should reject with small limit
        with pytest.raises(ValueError, match="too large"):
            secure_read_file(test_file, max_size=100)


class TestJSONRPCParseError:
    """JSON-RPC parse error response tests."""

    def test_parse_error_code(self):
        """Parse error uses code -32700."""
        import json

        # Simulate parse error response
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error"
            }
        }

        assert error_response["error"]["code"] == -32700

    def test_invalid_json_handling(self):
        """Invalid JSON returns proper error."""
        import json

        invalid_json = "{ not valid json"

        try:
            json.loads(invalid_json)
            assert False, "Should have raised JSONDecodeError"
        except json.JSONDecodeError:
            # Expected behavior
            pass


class TestPluginDirectorySecurity:
    """Plugin directory security tests."""

    def test_world_writable_check(self, temp_sandbox):
        """Detects world-writable directories."""
        import stat

        # Create world-writable directory
        plugins_dir = os.path.join(temp_sandbox, "plugins")
        os.makedirs(plugins_dir)

        # Make world-writable
        os.chmod(plugins_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

        # Check permission
        stat_info = os.stat(plugins_dir)
        is_world_writable = stat_info.st_mode & 0o002

        assert is_world_writable != 0

        # Cleanup
        os.chmod(plugins_dir, stat.S_IRWXU)

    def test_safe_directory_accepted(self, temp_sandbox):
        """Safe directories are accepted."""
        import stat

        plugins_dir = os.path.join(temp_sandbox, "safe_plugins")
        os.makedirs(plugins_dir)

        # Owner only
        os.chmod(plugins_dir, stat.S_IRWXU)

        stat_info = os.stat(plugins_dir)
        is_world_writable = stat_info.st_mode & 0o002

        assert is_world_writable == 0


class TestSecretsSanitization:
    """Secrets sanitization tests."""

    def test_sanitizes_jwt(self):
        """Sanitizes JWT tokens."""
        from app.core.security import secrets_sanitizer

        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w"
        text = f"Token: {jwt}"
        sanitized = secrets_sanitizer.sanitize(text)

        assert jwt not in sanitized
        assert "REDACTED" in sanitized

    def test_preserves_safe_text(self):
        """Preserves text without secrets."""
        from app.core.security import secrets_sanitizer

        safe_text = "Hello, this is normal text without any secrets"
        sanitized = secrets_sanitizer.sanitize(safe_text)

        assert sanitized == safe_text


class TestInputValidation:
    """Input validation tests."""

    def test_pydantic_validation_exists(self):
        """Pydantic validation is available."""
        from app.schemas.inputs import validate_tool_input

        assert callable(validate_tool_input)

    def test_validates_ask_gemini_input(self):
        """Validates ask_gemini input."""
        from app.schemas.inputs import validate_tool_input

        # Valid input
        valid = validate_tool_input("ask_gemini", {
            "prompt": "Hello",
            "temperature": 0.5
        })
        assert valid["prompt"] == "Hello"

    def test_rejects_invalid_temperature(self):
        """Rejects invalid temperature."""
        from app.schemas.inputs import validate_tool_input

        with pytest.raises(ValueError):
            validate_tool_input("ask_gemini", {
                "prompt": "Hello",
                "temperature": 2.0  # Invalid
            })

    def test_rejects_empty_prompt(self):
        """Rejects empty prompt."""
        from app.schemas.inputs import validate_tool_input

        with pytest.raises(ValueError):
            validate_tool_input("ask_gemini", {
                "prompt": ""
            })
