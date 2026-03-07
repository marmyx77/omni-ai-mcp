"""
Unit tests for validate_path function.

Tests path sandboxing and security validation.
"""

import pytest
import os
from pathlib import Path


class TestValidatePath:
    """Tests for validate_path security function."""

    def test_accepts_path_in_sandbox(self, temp_sandbox):
        """Accepts paths within the sandbox."""
        from app.core.security import validate_path

        file_path = f"{temp_sandbox}/valid_file.py"
        result = validate_path(file_path)

        # Should return the path (or resolved path)
        assert result is not None
        assert "valid_file.py" in result

    def test_rejects_path_outside_sandbox(self, sandbox_enabled):
        """Rejects paths outside the sandbox."""
        from app.core.security import validate_path

        with pytest.raises((ValueError, PermissionError)) as exc_info:
            validate_path("/etc/passwd")

        assert "sandbox" in str(exc_info.value).lower() or "outside" in str(exc_info.value).lower()

    def test_rejects_directory_traversal(self, sandbox_enabled):
        """Rejects directory traversal attempts."""
        from app.core.security import validate_path

        traversal_path = f"{sandbox_enabled}/../../../etc/passwd"

        with pytest.raises((ValueError, PermissionError)):
            validate_path(traversal_path)

    def test_resolves_symlinks(self, temp_sandbox):
        """Resolves symlinks and checks destination."""
        from app.core.security import validate_path

        # Create a file and symlink inside sandbox
        real_file = Path(temp_sandbox) / "real.txt"
        real_file.write_text("content")

        link_file = Path(temp_sandbox) / "link.txt"
        link_file.symlink_to(real_file)

        # Should accept link to file in sandbox
        result = validate_path(str(link_file))
        assert result is not None

    def test_rejects_symlink_to_outside(self, sandbox_enabled):
        """Rejects symlinks pointing outside sandbox."""
        from app.core.security import validate_path
        import tempfile

        # Create file outside sandbox
        outside_file = tempfile.NamedTemporaryFile(delete=False)
        outside_file.write(b"secret")
        outside_file.close()

        link_path = None
        try:
            # Create symlink inside sandbox pointing outside
            link_path = Path(sandbox_enabled) / "malicious_link.txt"
            link_path.symlink_to(outside_file.name)

            with pytest.raises((ValueError, PermissionError)):
                validate_path(str(link_path))
        finally:
            os.unlink(outside_file.name)
            if link_path and link_path.exists():
                link_path.unlink()

    def test_accepts_relative_paths_in_sandbox(self, temp_sandbox):
        """Accepts relative paths that resolve to sandbox."""
        from app.core.security import validate_path
        import os

        # Change to sandbox directory
        old_cwd = os.getcwd()
        os.chdir(temp_sandbox)

        try:
            result = validate_path("./relative_file.py")
            assert result is not None
        finally:
            os.chdir(old_cwd)

    def test_accepts_nested_directories(self, temp_sandbox):
        """Accepts deeply nested paths in sandbox."""
        from app.core.security import validate_path

        nested_path = f"{temp_sandbox}/a/b/c/d/e/file.py"
        result = validate_path(nested_path)

        assert result is not None
        assert "file.py" in result

    def test_handles_nonexistent_path(self, temp_sandbox):
        """Handles nonexistent paths (for write validation)."""
        from app.core.security import validate_path

        new_file = f"{temp_sandbox}/nonexistent/new_file.py"
        # Should not raise for nonexistent paths in sandbox
        result = validate_path(new_file)

        assert result is not None


class TestValidatePathEdgeCases:
    """Edge case tests for validate_path."""

    def test_empty_path(self, temp_sandbox):
        """Handles empty path."""
        from app.core.security import validate_path

        # Empty path should either raise or return current directory
        result = validate_path("")
        # If it doesn't raise, it should return something valid
        assert isinstance(result, str)

    def test_path_with_special_characters(self, temp_sandbox):
        """Handles paths with special characters."""
        from app.core.security import validate_path

        special_path = f"{temp_sandbox}/file with spaces.py"
        result = validate_path(special_path)

        assert result is not None

    def test_path_with_unicode(self, temp_sandbox):
        """Handles paths with unicode characters."""
        from app.core.security import validate_path

        unicode_path = f"{temp_sandbox}/файл.py"
        result = validate_path(unicode_path)

        assert result is not None
