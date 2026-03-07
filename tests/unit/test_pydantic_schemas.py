"""
Unit tests for Pydantic input validation schemas.

Tests type validation, defaults, and error handling.
"""

import pytest


class TestValidateToolInput:
    """Tests for validate_tool_input function."""

    def test_valid_ask_gemini_input(self):
        """Valid input passes validation."""
        from app.schemas.inputs import validate_tool_input

        args = {'prompt': 'Hello', 'model': 'pro', 'temperature': 0.7}
        result = validate_tool_input('ask_gemini', args)

        assert result['prompt'] == 'Hello'
        assert result['model'] == 'pro'
        assert result['temperature'] == 0.7

    def test_defaults_applied(self):
        """Default values are applied for missing fields."""
        from app.schemas.inputs import validate_tool_input

        args = {'prompt': 'Test'}
        result = validate_tool_input('ask_gemini', args)

        assert result['model'] == 'pro'
        assert result['temperature'] == 0.5
        assert result['thinking_level'] == 'off'
        assert result['include_thoughts'] is False

    def test_enum_serialized_to_string(self):
        """Enums are serialized to string values."""
        from app.schemas.inputs import validate_tool_input

        args = {'prompt': 'Test', 'thinking_level': 'high'}
        result = validate_tool_input('ask_gemini', args)

        assert isinstance(result['thinking_level'], str)
        assert result['thinking_level'] == 'high'

    def test_invalid_temperature_rejected(self):
        """Temperature outside range raises error."""
        from app.schemas.inputs import validate_tool_input

        args = {'prompt': 'Test', 'temperature': 2.0}

        with pytest.raises(ValueError) as exc_info:
            validate_tool_input('ask_gemini', args)

        assert 'temperature' in str(exc_info.value).lower()

    def test_invalid_model_rejected(self):
        """Invalid model value raises error."""
        from app.schemas.inputs import validate_tool_input

        args = {'prompt': 'Test', 'model': 'invalid_model'}

        with pytest.raises(ValueError) as exc_info:
            validate_tool_input('ask_gemini', args)

        assert 'model' in str(exc_info.value).lower()

    def test_missing_required_field_rejected(self):
        """Missing required field raises error."""
        from app.schemas.inputs import validate_tool_input

        args = {'model': 'pro'}  # Missing 'prompt'

        with pytest.raises(ValueError) as exc_info:
            validate_tool_input('ask_gemini', args)

        assert 'prompt' in str(exc_info.value).lower()

    def test_empty_prompt_rejected(self):
        """Empty prompt raises error."""
        from app.schemas.inputs import validate_tool_input

        args = {'prompt': ''}

        with pytest.raises(ValueError) as exc_info:
            validate_tool_input('ask_gemini', args)

        assert 'prompt' in str(exc_info.value).lower()

    def test_unknown_tool_passes_through(self):
        """Unknown tools pass through without validation."""
        from app.schemas.inputs import validate_tool_input

        args = {'any': 'value', 'unknown': 123}
        result = validate_tool_input('unknown_tool', args)

        assert result == args


class TestGenerateCodeInput:
    """Tests for GenerateCodeInput schema."""

    def test_null_context_files_handled(self):
        """Null context_files converted to empty list."""
        from app.schemas.inputs import validate_tool_input

        args = {'prompt': 'Create function', 'context_files': None}
        result = validate_tool_input('gemini_generate_code', args)

        assert result['context_files'] == []

    def test_context_files_preserved(self):
        """Non-null context_files preserved."""
        from app.schemas.inputs import validate_tool_input

        files = ['@file1.py', '@file2.py']
        args = {'prompt': 'Create function', 'context_files': files}
        result = validate_tool_input('gemini_generate_code', args)

        assert result['context_files'] == files

    def test_style_enum_values(self):
        """Style enum values work correctly."""
        from app.schemas.inputs import validate_tool_input

        for style in ['production', 'prototype', 'minimal']:
            args = {'prompt': 'Test', 'style': style}
            result = validate_tool_input('gemini_generate_code', args)
            assert result['style'] == style

    def test_language_options(self):
        """Language options validated."""
        from app.schemas.inputs import validate_tool_input

        languages = ['auto', 'python', 'typescript', 'javascript', 'rust', 'go']
        for lang in languages:
            args = {'prompt': 'Test', 'language': lang}
            result = validate_tool_input('gemini_generate_code', args)
            assert result['language'] == lang


class TestChallengeInput:
    """Tests for ChallengeInput schema."""

    def test_focus_options(self):
        """Focus enum values work correctly."""
        from app.schemas.inputs import validate_tool_input

        focus_options = ['general', 'security', 'performance',
                         'maintainability', 'scalability', 'cost']

        for focus in focus_options:
            args = {'statement': 'Test idea', 'focus': focus}
            result = validate_tool_input('gemini_challenge', args)
            assert result['focus'] == focus

    def test_context_default_empty(self):
        """Context defaults to empty string."""
        from app.schemas.inputs import validate_tool_input

        args = {'statement': 'Test'}
        result = validate_tool_input('gemini_challenge', args)

        assert result['context'] == ''


class TestAnalyzeCodebaseInput:
    """Tests for AnalyzeCodebaseInput schema."""

    def test_files_required(self):
        """Files field is required."""
        from app.schemas.inputs import validate_tool_input

        args = {'prompt': 'Analyze'}

        with pytest.raises(ValueError) as exc_info:
            validate_tool_input('gemini_analyze_codebase', args)

        assert 'files' in str(exc_info.value).lower()

    def test_analysis_type_options(self):
        """Analysis type enum values work."""
        from app.schemas.inputs import validate_tool_input

        types = ['architecture', 'security', 'refactoring',
                 'documentation', 'dependencies', 'general']

        for atype in types:
            args = {'prompt': 'Analyze', 'files': ['*.py'], 'analysis_type': atype}
            result = validate_tool_input('gemini_analyze_codebase', args)
            assert result['analysis_type'] == atype


class TestBrainstormInput:
    """Tests for BrainstormInput schema."""

    def test_idea_count_range(self):
        """Idea count must be in valid range."""
        from app.schemas.inputs import validate_tool_input

        # Valid
        args = {'topic': 'Test', 'idea_count': 10}
        result = validate_tool_input('gemini_brainstorm', args)
        assert result['idea_count'] == 10

        # Too low
        with pytest.raises(ValueError):
            validate_tool_input('gemini_brainstorm', {'topic': 'Test', 'idea_count': 0})

        # Too high
        with pytest.raises(ValueError):
            validate_tool_input('gemini_brainstorm', {'topic': 'Test', 'idea_count': 100})

    def test_methodology_options(self):
        """Methodology enum values work."""
        from app.schemas.inputs import validate_tool_input

        methods = ['auto', 'divergent', 'convergent', 'scamper',
                   'design-thinking', 'lateral']

        for method in methods:
            args = {'topic': 'Test', 'methodology': method}
            result = validate_tool_input('gemini_brainstorm', args)
            assert result['methodology'] == method
