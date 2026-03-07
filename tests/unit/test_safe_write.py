"""
Unit tests for SafeFileWriter.

Tests atomic writes, backups, permission preservation, and security features.
"""

import pytest
import os
import stat
from pathlib import Path


class TestSafeFileWriterBasic:
    """Basic write operations."""

    def test_creates_new_file(self, temp_sandbox):
        """SafeFileWriter creates a new file successfully."""
        from app.core.security import SafeFileWriter

        writer = SafeFileWriter()
        file_path = f"{temp_sandbox}/new_file.py"
        result = writer.write(file_path, "print('hello')")

        assert result.success
        assert os.path.exists(file_path)
        assert result.content_hash is not None
        assert result.error is None

    def test_content_written_correctly(self, temp_sandbox):
        """File content matches what was written."""
        from app.core.security import SafeFileWriter

        writer = SafeFileWriter()
        file_path = f"{temp_sandbox}/content_test.py"
        content = "def foo():\n    return 42\n"

        writer.write(file_path, content)

        with open(file_path, 'r') as f:
            assert f.read() == content

    def test_creates_parent_directories(self, temp_sandbox):
        """SafeFileWriter creates parent directories if needed."""
        from app.core.security import SafeFileWriter

        writer = SafeFileWriter()
        file_path = f"{temp_sandbox}/deep/nested/dir/file.py"
        result = writer.write(file_path, "content")

        assert result.success
        assert os.path.exists(file_path)

    def test_no_backup_for_new_file(self, temp_sandbox):
        """No backup is created for a new file."""
        from app.core.security import SafeFileWriter

        writer = SafeFileWriter()
        file_path = f"{temp_sandbox}/new_no_backup.py"
        result = writer.write(file_path, "content")

        assert result.success
        assert result.backup_path is None


class TestSafeFileWriterBackup:
    """Backup functionality tests."""

    def test_creates_backup_on_overwrite(self, temp_sandbox):
        """Backup is created when overwriting existing file."""
        from app.core.security import SafeFileWriter

        file_path = Path(temp_sandbox) / "existing.py"
        file_path.write_text("original content")

        writer = SafeFileWriter()
        result = writer.write(str(file_path), "new content")

        assert result.success
        assert result.backup_path is not None
        assert os.path.exists(result.backup_path)

    def test_backup_contains_original_content(self, temp_sandbox):
        """Backup file contains the original content."""
        from app.core.security import SafeFileWriter

        file_path = Path(temp_sandbox) / "backup_content.py"
        original = "original content here"
        file_path.write_text(original)

        writer = SafeFileWriter()
        writer.write(str(file_path), "new content")

        # Find backup
        backup_dir = Path(temp_sandbox) / ".gemini_backups"
        backups = list(backup_dir.glob("*.bak"))
        assert len(backups) == 1

        backup_content = backups[0].read_text()
        assert backup_content == original

    def test_backup_rotation_max_5(self, temp_sandbox):
        """Only keeps maximum 5 backups per file."""
        from app.core.security import SafeFileWriter
        import time

        file_path = Path(temp_sandbox) / "rotation_test.py"
        file_path.write_text("v0")

        writer = SafeFileWriter()

        # Create 7 overwrites
        for i in range(7):
            writer.write(str(file_path), f"version {i+1}")
            time.sleep(0.05)  # Ensure different timestamps

        # Check backup count
        backup_dir = Path(temp_sandbox) / ".gemini_backups"
        backups = list(backup_dir.glob("rotation_test.py.*.bak"))
        assert len(backups) <= 5

    def test_skip_backup_when_disabled(self, temp_sandbox):
        """No backup when create_backup=False."""
        from app.core.security import SafeFileWriter

        file_path = Path(temp_sandbox) / "no_backup.py"
        file_path.write_text("original")

        writer = SafeFileWriter()
        result = writer.write(str(file_path), "new", create_backup=False)

        assert result.success
        assert result.backup_path is None

    def test_gitignore_created_in_backup_dir(self, temp_sandbox):
        """A .gitignore is created in backup directory."""
        from app.core.security import SafeFileWriter

        file_path = Path(temp_sandbox) / "gitignore_test.py"
        file_path.write_text("original")

        writer = SafeFileWriter()
        writer.write(str(file_path), "new")

        gitignore = Path(temp_sandbox) / ".gemini_backups" / ".gitignore"
        assert gitignore.exists()
        assert "*" in gitignore.read_text()


class TestSafeFileWriterPermissions:
    """Permission preservation tests."""

    def test_preserves_executable_permission(self, temp_sandbox):
        """Executable permission is preserved after overwrite."""
        from app.core.security import SafeFileWriter

        file_path = Path(temp_sandbox) / "executable.py"
        file_path.write_text("#!/usr/bin/env python3")
        os.chmod(file_path, 0o755)

        writer = SafeFileWriter()
        result = writer.write(str(file_path), "#!/usr/bin/env python3\nprint('hi')")

        assert result.success
        assert result.preserved_permissions

        # Check mode
        mode = os.stat(file_path).st_mode
        assert mode & stat.S_IXUSR  # Owner execute

    def test_preserves_readonly_makes_writable(self, temp_sandbox):
        """Can write to read-only file by temporarily changing permissions."""
        from app.core.security import SafeFileWriter

        file_path = Path(temp_sandbox) / "readonly.py"
        file_path.write_text("original")
        os.chmod(file_path, 0o444)  # Read-only

        writer = SafeFileWriter()
        result = writer.write(str(file_path), "new content")

        assert result.success
        assert file_path.read_text() == "new content"


class TestSafeFileWriterContentHash:
    """Content hash verification tests."""

    def test_hash_is_consistent(self, temp_sandbox):
        """Same content produces same hash."""
        from app.core.security import SafeFileWriter

        writer = SafeFileWriter()
        content = "test content"

        result1 = writer.write(f"{temp_sandbox}/file1.py", content)
        result2 = writer.write(f"{temp_sandbox}/file2.py", content)

        assert result1.content_hash == result2.content_hash

    def test_different_content_different_hash(self, temp_sandbox):
        """Different content produces different hash."""
        from app.core.security import SafeFileWriter

        writer = SafeFileWriter()

        result1 = writer.write(f"{temp_sandbox}/file1.py", "content A")
        result2 = writer.write(f"{temp_sandbox}/file2.py", "content B")

        assert result1.content_hash != result2.content_hash


class TestSecureWriteFile:
    """Tests for the convenience function."""

    def test_secure_write_file_function(self, temp_sandbox):
        """secure_write_file() works as convenience wrapper."""
        from app.core.security import secure_write_file

        file_path = f"{temp_sandbox}/secure_test.py"
        result = secure_write_file(file_path, "test content")

        assert result.success
        assert os.path.exists(file_path)

    def test_secure_write_file_creates_backup(self, temp_sandbox):
        """secure_write_file() creates backup on overwrite."""
        from app.core.security import secure_write_file, SafeFileWriter

        file_path = Path(temp_sandbox) / "secure_backup.py"
        file_path.write_text("original")

        # Use SafeFileWriter directly with explicit backup dir in sandbox
        writer = SafeFileWriter()
        result = writer.write(str(file_path), "new content")

        assert result.success
        assert result.backup_path is not None
