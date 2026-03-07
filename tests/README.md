# Test Suite - omni-ai-mcp

## Structure

```
tests/
├── conftest.py          # Shared fixtures (10 fixtures)
├── unit/                # Unit tests (105 tests)
│   ├── test_add_line_numbers.py
│   ├── test_expand_file_references.py
│   ├── test_parse_generated_code.py
│   ├── test_pydantic_schemas.py
│   ├── test_safe_write.py
│   ├── test_secrets_sanitizer.py
│   └── test_validate_path.py
└── integration/         # Integration tests (125 tests)
    ├── test_backward_compat.py
    ├── test_fastmcp_server.py
    ├── test_mcp_tools.py
    ├── test_security_v3.py
    ├── test_sqlite_persistence.py
    └── real_outputs/    # Captured real outputs (for reference)
```

## Test Categories

### Unit Tests (`tests/unit/`)
Fast, isolated tests for individual functions and utilities:
- **Security**: Path validation, secrets sanitization
- **File operations**: Safe writes, line numbering, file references
- **Validation**: Pydantic schemas, code parsing

### Integration Tests (`tests/integration/`)
Tests for the complete FastMCP server and component interaction:
- **Server**: FastMCP initialization, tool registration
- **Tools**: All 15 MCP tools with mocked Gemini API
- **Persistence**: SQLite database operations, thread safety
- **Compatibility**: Deprecated module imports and shims

## Running Tests

```bash
# All tests
python3 -m pytest tests/ -v

# Unit tests only (fast)
python3 -m pytest tests/unit/ -v

# Integration tests only
python3 -m pytest tests/integration/ -v

# Specific test file
python3 -m pytest tests/unit/test_safe_write.py -v

# With coverage
python3 -m pytest tests/ --cov=app --cov-report=html

# Stop on first failure
python3 -m pytest tests/ -x
```

## Available Fixtures

Defined in `conftest.py`:

| Fixture | Description |
|---------|-------------|
| `temp_sandbox` | Temporary directory with sandbox disabled |
| `sandbox_enabled` | Temporary directory with sandbox checking enabled |
| `temp_file` | Pre-created test file in sandbox |
| `sample_python_file` | Python file with sample functions |
| `sample_generated_code_xml` | XML output sample for code generation |
| `sample_need_files_json` | JSON sample for More Info Protocol |
| `mock_gemini_client` | Mocked Gemini API client |
| `mock_conversation_memory` | Mocked conversation memory |
| `disable_logging` | Disable activity logging |
| `test_files_dir` | Directory with various file types |

## Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*` (e.g., `TestSafeFileWriterBasic`)
- Test methods: `test_*` (e.g., `test_creates_new_file`)

## Writing New Tests

```python
import pytest
from app.core.security import validate_path

class TestMyFeature:
    """Tests for my feature."""

    def test_basic_functionality(self, temp_sandbox):
        """Test basic case."""
        # Use fixtures for setup
        result = my_function()
        assert result == expected

    def test_edge_case(self, sandbox_enabled):
        """Test with sandbox enabled."""
        with pytest.raises(ValueError):
            my_function_that_fails()
```

## Dependencies

Install dev dependencies:
```bash
pip install -e ".[dev]"
```

Required packages:
- `pytest>=7.0.0`
- `pytest-cov>=4.0.0`
- `pytest-asyncio>=0.21.0`
