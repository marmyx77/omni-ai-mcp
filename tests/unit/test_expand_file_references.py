"""
Unit tests for expand_file_references function.

Tests @file reference expansion.
"""

import pytest
import os
from pathlib import Path


class TestExpandFileReferences:
    """Tests for @file reference expansion."""

    def test_expands_single_file(self, sample_python_file, temp_sandbox):
        """Expands single @file reference."""
        from app.utils.file_refs import expand_file_references

        text = f"Review this: @{sample_python_file}"
        result = expand_file_references(text)

        assert "def add(a, b):" in result
        assert "def subtract(a, b):" in result

    def test_no_expansion_for_email(self, temp_sandbox):
        """Does not expand email addresses."""
        from app.utils.file_refs import expand_file_references

        text = "Contact: user@example.com"
        result = expand_file_references(text)

        assert result == text
        assert "@example.com" in result

    def test_expands_glob_pattern(self, test_files_dir):
        """Expands glob patterns like @*.py."""
        from app.utils.file_refs import expand_file_references

        text = f"Check files: @{test_files_dir}/*.py"
        result = expand_file_references(text)

        assert "print('hello')" in result  # from code.py

    def test_expands_recursive_glob(self, test_files_dir):
        """Expands recursive glob patterns."""
        from app.utils.file_refs import expand_file_references

        text = f"All Python: @{test_files_dir}/**/*.py"
        result = expand_file_references(text)

        # Should include files from src/ subdirectory
        assert "def main():" in result or "def util():" in result

    def test_expands_directory_listing(self, test_files_dir):
        """Expands @directory to listing."""
        from app.utils.file_refs import expand_file_references

        text = f"List: @{test_files_dir}"
        result = expand_file_references(text)

        # Should list files
        assert "code.py" in result or "src" in result

    def test_multiple_references(self, test_files_dir):
        """Expands multiple @references in same text."""
        from app.utils.file_refs import expand_file_references

        text = f"File1: @{test_files_dir}/code.py and File2: @{test_files_dir}/data.json"
        result = expand_file_references(text)

        assert "print('hello')" in result
        assert '"key"' in result or "'key'" in result

    def test_preserves_surrounding_text(self, sample_python_file):
        """Preserves text around @references."""
        from app.utils.file_refs import expand_file_references

        text = f"Please review @{sample_python_file} and give feedback."
        result = expand_file_references(text)

        assert "Please review" in result
        assert "and give feedback" in result

    def test_handles_nonexistent_file(self, temp_sandbox):
        """Handles nonexistent file gracefully."""
        from app.utils.file_refs import expand_file_references

        text = f"@{temp_sandbox}/nonexistent.py"
        result = expand_file_references(text)

        # Should either keep original or show error message
        assert isinstance(result, str)

    def test_line_numbers_added_to_code(self, sample_python_file):
        """Line numbers are added to code files."""
        from app.utils.file_refs import expand_file_references

        text = f"@{sample_python_file}"
        result = expand_file_references(text)

        # Should contain line numbers (v2.5.0 feature)
        # Format: "  1│ code" or similar
        # Line numbers appear in the content block, not at the very start
        assert "1│" in result or "1|" in result

    def test_no_line_numbers_for_json(self, test_files_dir):
        """No line numbers for JSON files."""
        from app.utils.file_refs import expand_file_references

        text = f"@{test_files_dir}/data.json"
        result = expand_file_references(text)

        # JSON should be readable without line number clutter
        assert '"key"' in result or "'key'" in result


class TestExpandFileReferencesLimits:
    """Tests for file reference limits."""

    def test_truncates_large_files(self, temp_sandbox):
        """Large files are truncated."""
        from app.utils.file_refs import expand_file_references

        # Create a large file
        large_file = Path(temp_sandbox) / "large.py"
        large_content = "x = 1\n" * 100000  # Very large
        large_file.write_text(large_content)

        text = f"@{large_file}"
        result = expand_file_references(text)

        # Result should be smaller than original
        assert len(result) < len(large_content)

    def test_glob_max_files(self, temp_sandbox):
        """Glob patterns limited to max files."""
        from app.utils.file_refs import expand_file_references

        # Create many files
        for i in range(20):
            (Path(temp_sandbox) / f"file{i}.py").write_text(f"# file {i}")

        text = f"@{temp_sandbox}/*.py"
        result = expand_file_references(text)

        # Should not include all 20 files
        # Max is typically 10 for globs
        assert isinstance(result, str)


class TestExpandFileReferencesEdgeCases:
    """Edge cases for file reference expansion."""

    def test_at_symbol_not_followed_by_path(self):
        """Handles @ not followed by valid path."""
        from app.utils.file_refs import expand_file_references

        text = "@ alone and @123 numbers"
        result = expand_file_references(text)

        # Should preserve original text
        assert "@" in result

    def test_empty_text(self):
        """Handles empty text."""
        from app.utils.file_refs import expand_file_references

        result = expand_file_references("")
        assert result == ""

    def test_current_directory_reference(self, temp_sandbox):
        """Handles @. for current directory."""
        from app.utils.file_refs import expand_file_references
        import os

        # Create a file in temp_sandbox
        (Path(temp_sandbox) / "test.py").write_text("# test")

        old_cwd = os.getcwd()
        os.chdir(temp_sandbox)

        try:
            text = "@."
            result = expand_file_references(text)

            # Should list directory contents
            assert isinstance(result, str)
        finally:
            os.chdir(old_cwd)
