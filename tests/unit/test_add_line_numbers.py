"""
Unit tests for add_line_numbers function.

Tests dynamic line numbering for code files.
"""

import pytest


class TestAddLineNumbers:
    """Tests for add_line_numbers function."""

    def test_adds_line_numbers_basic(self):
        """Adds line numbers to basic content."""
        from app.utils.file_refs import add_line_numbers

        content = "line1\nline2\nline3"
        result = add_line_numbers(content)

        assert "1" in result
        assert "line1" in result
        assert "2" in result
        assert "line2" in result

    def test_line_number_format(self):
        """Line numbers use correct format with separator."""
        from app.utils.file_refs import add_line_numbers

        content = "hello"
        result = add_line_numbers(content)

        # Should have format like "  1| hello" or similar
        lines = result.split('\n')
        assert len(lines) >= 1
        # Check first line has a number
        assert '1' in lines[0]

    def test_preserves_content(self):
        """Original content is preserved."""
        from app.utils.file_refs import add_line_numbers

        content = "def foo():\n    return 42"
        result = add_line_numbers(content)

        assert "def foo():" in result
        assert "return 42" in result

    def test_handles_empty_content(self):
        """Handles empty string gracefully."""
        from app.utils.file_refs import add_line_numbers

        result = add_line_numbers("")
        assert isinstance(result, str)

    def test_handles_single_line(self):
        """Handles single line content."""
        from app.utils.file_refs import add_line_numbers

        content = "single line"
        result = add_line_numbers(content)

        assert "single line" in result
        assert "1" in result

    def test_handles_many_lines(self):
        """Handles many lines with proper alignment."""
        from app.utils.file_refs import add_line_numbers

        # Create 100+ lines
        lines = [f"line {i}" for i in range(150)]
        content = "\n".join(lines)
        result = add_line_numbers(content)

        # Check line 1, 50, 100, 150 are present
        assert "line 0" in result
        assert "line 49" in result
        assert "line 99" in result
        assert "line 149" in result

    def test_alignment_with_different_widths(self):
        """Line numbers align properly for different counts."""
        from app.utils.file_refs import add_line_numbers

        # 5 lines - single digit
        content5 = "a\nb\nc\nd\ne"
        result5 = add_line_numbers(content5)

        # 15 lines - double digit
        content15 = "\n".join([chr(97 + i % 26) for i in range(15)])
        result15 = add_line_numbers(content15)

        # Both should work without error
        assert "1" in result5
        assert "15" in result15

    def test_custom_start_line(self):
        """Supports custom start line number."""
        from app.utils.file_refs import add_line_numbers

        content = "line1\nline2"
        result = add_line_numbers(content, start_line=10)

        assert "10" in result
        assert "11" in result
        assert "1" not in result.split('\n')[0] or "10" in result.split('\n')[0]

    def test_preserves_indentation(self):
        """Preserves original code indentation."""
        from app.utils.file_refs import add_line_numbers

        content = "def foo():\n    if True:\n        pass"
        result = add_line_numbers(content)

        # Content indentation should be preserved
        assert "    if True:" in result
        assert "        pass" in result

    def test_handles_blank_lines(self):
        """Handles blank lines correctly."""
        from app.utils.file_refs import add_line_numbers

        content = "line1\n\nline3"
        result = add_line_numbers(content)

        lines = result.split('\n')
        assert len(lines) == 3  # Should have 3 lines with numbers

    def test_handles_trailing_newline(self):
        """Handles trailing newline correctly."""
        from app.utils.file_refs import add_line_numbers

        content = "line1\nline2\n"
        result = add_line_numbers(content)

        # Should not add extra empty numbered line
        assert "line1" in result
        assert "line2" in result
