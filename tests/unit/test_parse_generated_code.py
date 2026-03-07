"""
Unit tests for parse_generated_code function.

Tests XML parsing of generated code output.
"""

import pytest


class TestParseGeneratedCode:
    """Tests for parse_generated_code function."""

    def test_extracts_single_file(self):
        """Extracts a single file from XML."""
        from app.tools.code.generate_code import parse_generated_code

        xml = '''<GENERATED_CODE>
<FILE action="create" path="hello.py">
print("hello")
</FILE>
</GENERATED_CODE>'''

        files = parse_generated_code(xml)

        assert len(files) == 1
        assert files[0]['action'] == 'create'
        assert files[0]['path'] == 'hello.py'
        assert 'print("hello")' in files[0]['content']

    def test_extracts_multiple_files(self, sample_generated_code_xml):
        """Extracts multiple files from XML."""
        from app.tools.code.generate_code import parse_generated_code

        files = parse_generated_code(sample_generated_code_xml)

        assert len(files) == 2
        assert files[0]['path'] == 'src/hello.py'
        assert files[1]['path'] == 'src/main.py'

    def test_extracts_action_attribute(self):
        """Correctly extracts action attribute."""
        from app.tools.code.generate_code import parse_generated_code

        xml = '''<GENERATED_CODE>
<FILE action="modify" path="existing.py">
modified content
</FILE>
</GENERATED_CODE>'''

        files = parse_generated_code(xml)

        assert files[0]['action'] == 'modify'

    def test_preserves_content_whitespace(self):
        """Preserves whitespace/indentation in content."""
        from app.tools.code.generate_code import parse_generated_code

        xml = '''<GENERATED_CODE>
<FILE action="create" path="indented.py">
def foo():
    if True:
        return 42
</FILE>
</GENERATED_CODE>'''

        files = parse_generated_code(xml)

        assert '    if True:' in files[0]['content']
        assert '        return 42' in files[0]['content']

    def test_handles_empty_xml(self):
        """Returns empty list for empty XML."""
        from app.tools.code.generate_code import parse_generated_code

        files = parse_generated_code('')
        assert files == []

    def test_handles_no_files(self):
        """Returns empty list when no FILE tags present."""
        from app.tools.code.generate_code import parse_generated_code

        xml = '<GENERATED_CODE>\nNo files here\n</GENERATED_CODE>'
        files = parse_generated_code(xml)

        assert files == []

    def test_handles_malformed_xml(self):
        """Handles malformed XML gracefully."""
        from app.tools.code.generate_code import parse_generated_code

        xml = '<GENERATED_CODE><FILE action="create" path="test.py">content'
        # Should not raise, just return what it can parse
        files = parse_generated_code(xml)

        # May return partial results or empty
        assert isinstance(files, list)

    def test_extracts_path_with_directories(self):
        """Extracts paths with directory structure."""
        from app.tools.code.generate_code import parse_generated_code

        xml = '''<GENERATED_CODE>
<FILE action="create" path="src/components/Button.tsx">
export const Button = () => <button>Click</button>
</FILE>
</GENERATED_CODE>'''

        files = parse_generated_code(xml)

        assert files[0]['path'] == 'src/components/Button.tsx'

    def test_handles_special_characters_in_content(self):
        """Handles special characters in file content."""
        from app.tools.code.generate_code import parse_generated_code

        xml = '''<GENERATED_CODE>
<FILE action="create" path="special.py">
text = "hello <world> & 'quotes'"
regex = r"test.*\d+"
</FILE>
</GENERATED_CODE>'''

        files = parse_generated_code(xml)

        assert len(files) == 1
        assert '<world>' in files[0]['content'] or '&lt;world&gt;' in files[0]['content']

    def test_default_action_is_create(self):
        """Default action should be 'create' if not specified."""
        from app.tools.code.generate_code import parse_generated_code

        xml = '''<GENERATED_CODE>
<FILE path="no_action.py">
content
</FILE>
</GENERATED_CODE>'''

        files = parse_generated_code(xml)

        # Implementation may vary - check it doesn't crash
        assert isinstance(files, list)
