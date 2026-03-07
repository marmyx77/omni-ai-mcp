# Contributing to omni-ai-mcp

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

Be respectful and constructive. We're all here to build something useful together.

## Current Version: 3.0.2

### Architecture Overview

The project uses a **modular architecture** with FastMCP SDK:

```
omni-ai-mcp/
├── run.py                    # Entry point
├── server.py                 # DEPRECATED: Backward compatibility shim
├── pyproject.toml            # Package configuration
├── app/
│   ├── __init__.py          # Package init, exports main(), __version__
│   ├── server.py            # FastMCP server (15 @mcp.tool() registrations)
│   ├── __main__.py          # DEPRECATED: Legacy JSON-RPC handler
│   ├── core/                # Infrastructure
│   │   ├── config.py        # Configuration & version
│   │   ├── logging.py       # Structured JSON logging
│   │   └── security.py      # Sandboxing, sanitization, SafeFileWriter
│   ├── services/            # External integrations
│   │   ├── gemini.py        # Gemini client with fallback
│   │   ├── persistence.py   # SQLite conversation storage (PRIMARY)
│   │   └── memory.py        # DEPRECATED: In-memory cache
│   ├── tools/               # MCP tools (15 total, organized by domain)
│   │   ├── registry.py      # @tool decorator
│   │   ├── text/            # ask_gemini, code_review, brainstorm, challenge
│   │   ├── code/            # analyze_codebase (5MB limit), generate_code (dry-run)
│   │   ├── media/           # image/video generation (async polling), TTS, vision
│   │   ├── web/             # web_search
│   │   └── rag/             # file_store, file_search, upload
│   ├── utils/               # Helpers (file_refs, tokens)
│   ├── schemas/             # Pydantic v2 validation
│   └── middleware/          # Request processing
└── tests/                   # Test suite (230 tests)
    ├── unit/                # Unit tests (105 tests)
    └── integration/         # Integration tests (125 tests)
```

### Recent Releases
- **v3.0.2** - ReDoS Fix, defusedxml Parser, File Locking, DB Permissions, Binary Detection
- **v3.0.1** - Security Hardening, Dry-Run Mode, Async Video Polling, Deprecation Warnings
- **v3.0.0** - FastMCP SDK, SQLite Persistence, Security Fixes
- **v2.7.0** - Docker Support, Structured JSON Logging

### Deprecated Modules (Remove in v4.0.0)

| Module | Replacement | Notes |
|--------|-------------|-------|
| `app/__main__.py` | `app/server.py` | Use FastMCP server |
| `app/services/memory.py` | `app/services/persistence.py` | SQLite survives restarts |
| `server.py` (root) | Import from `app/` | Backward compatibility shim |

### Planned Features (Contributions Welcome!)

| Feature | Priority | Complexity | Description |
|---------|----------|------------|-------------|
| Full Async Tools | High | High | Convert all tools to `async def` |
| Streaming Responses | High | Medium | Stream `ask_gemini` results |
| Plugin SDK | Medium | Medium | Third-party tool plugins |
| CLI Wizard | Low | Low | Interactive setup command |
| Rate Limiting | Low | Medium | Per-tool rate limits |
| SSRF Mitigation | Low | Medium | URL validation for web tools |

### Easy First Contributions

1. **Test Coverage** - Add unit tests for untested functions
2. **Documentation** - Improve examples and use cases
3. **Voice Samples** - Document TTS voice characteristics
4. **Error Messages** - Improve user-facing error messages
5. **Implement Skipped Tests** - `test_restore_from_backup` feature

## How to Contribute

### Reporting Issues

1. Check if the issue already exists
2. Use a clear, descriptive title
3. Include:
   - Python version (3.9+ required)
   - Claude Code version
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages (if any)

### Suggesting Features

Open an issue with:
- Clear description of the feature
- Use case / why it's needed
- Example of how it would work

### Pull Requests

1. **Fork and clone** the repository
2. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following the code style below
4. **Test thoroughly**:
   ```bash
   # Quick verification
   python3 -c "
   from app.core.config import config
   print(f'Version: {config.version}')
   "

   # Run unit tests
   python3 -m pytest tests/unit/ -v

   # Test server starts
   GEMINI_API_KEY=your_key python3 run.py

   # Test in Claude Code
   ./setup.sh YOUR_KEY
   # Then test in Claude Code
   ```
5. **Submit PR** with:
   - Clear description of changes
   - Link to related issue (if any)
   - Screenshots/examples for UI changes

## Code Style

### Python Guidelines

- **Python 3.9+** compatibility required (FastMCP SDK requirement)
- **Type hints** for function parameters and returns
- **Docstrings** for public functions (Google style)
- **Self-contained** tool implementations (minimize dependencies between tools)
- **User-friendly errors** - return helpful messages, not stack traces

### Adding a New Tool

#### Step 1: Create the tool file

```python
# app/tools/domain/my_tool.py

from ...tools.registry import tool
from ...services import client, types, generate_with_fallback
from ...core import log_activity

MY_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "param": {"type": "string", "description": "Required parameter"},
        "optional": {"type": "string", "default": "default"}
    },
    "required": ["param"]
}

@tool(
    name="gemini_my_tool",
    description="Brief description of what the tool does",
    input_schema=MY_TOOL_SCHEMA,
    tags=["category"]
)
def my_tool(param: str, optional: str = "default") -> str:
    """
    Full description of the tool.

    Args:
        param: What this parameter does
        optional: What this optional parameter does

    Returns:
        Description of return value
    """
    try:
        response = generate_with_fallback(
            model_id="gemini-3-pro-preview",
            contents=param,
            config=types.GenerateContentConfig(temperature=0.5),
            operation="my_tool"
        )
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"
```

#### Step 2: Register in tools/domain/__init__.py

```python
# app/tools/domain/__init__.py
from . import my_tool
```

#### Step 3: Add Pydantic schema (recommended)

```python
# app/schemas/inputs.py

class MyToolInput(BaseModel):
    """Schema for gemini_my_tool input validation."""
    param: str = Field(..., min_length=1, description="Required param")
    optional: str = Field(default="default", description="Optional param")
```

### Security Guidelines

All file operations MUST use the security functions:

```python
from app.core.security import validate_path, secure_read_file, secure_write_file

# Reading files
content = secure_read_file(file_path)

# Writing files
result = secure_write_file(file_path, content)

# Validating paths
safe_path = validate_path(user_input)
```

**Security checklist for new tools:**
- [ ] Use `validate_path()` for any file path input
- [ ] Use `secure_read_file()` / `secure_write_file()` for file operations
- [ ] Never expose raw exception details to users
- [ ] Respect `SANDBOX_ROOT` boundaries
- [ ] Sanitize any logged data with `secrets_sanitizer`
- [ ] Sanitize LLM output before parsing (especially XML)

### v3.0.1 Security Features

When working with code generation or LLM output:

```python
from app.tools.code.generate_code import sanitize_xml_content, parse_generated_code

# Always sanitize LLM output before parsing
clean_xml = sanitize_xml_content(raw_llm_output)
files = parse_generated_code(clean_xml)
# parse_generated_code validates action types and blocks path traversal
```

## Testing

### Unit Tests

```bash
# Run all unit tests
python3 -m pytest tests/unit/ -v

# Run specific test file
python3 -m pytest tests/unit/test_safe_write.py -v

# Run with coverage
python3 -m pytest tests/ --cov=app --cov-report=html
```

### Quick Verification

```bash
# Verify imports and version
python3 -c "
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
from app.core.config import config
from app.tools.code.generate_code import parse_generated_code, sanitize_xml_content
from app.services.persistence import conversation_memory
print(f'Version: {config.version}')
print('All imports OK')
"
```

### Manual Testing

```bash
# 1. Test server initialization
echo '{"jsonrpc":"2.0","method":"initialize","id":1}' | \
  GEMINI_API_KEY=your_key python3 run.py

# 2. Test tools/list
echo '{"jsonrpc":"2.0","method":"tools/list","id":2}' | \
  GEMINI_API_KEY=your_key python3 run.py

# 3. Test a specific tool
echo '{"jsonrpc":"2.0","method":"tools/call","id":3,"params":{"name":"ask_gemini","arguments":{"prompt":"Hello"}}}' | \
  GEMINI_API_KEY=your_key python3 run.py
```

### MCP Integration Testing (Required)

Before submitting PRs that modify tools:

1. **Install to Claude Code**: `./setup.sh YOUR_KEY`
2. **Restart Claude Code**
3. **Test the modified tool via MCP**
4. **Verify no regressions in existing tools**

## Commit Messages

Use clear, descriptive messages:

```
Add gemini_my_tool for XYZ functionality

- Implement feature X with parameters Y and Z
- Add error handling for edge cases
- Add Pydantic validation schema
- Add unit tests
```

For version updates:
```
v3.0.1: Security hardening, dry-run mode, async polling

- Add XML sanitization to prevent injection attacks
- Add 5MB total byte limit to analyze_codebase
- Add dry_run parameter to generate_code
- Add async polling for video generation
- Add deprecation warnings to legacy modules
```

## Documentation

Update documentation when you:
- Add a new tool
- Change existing tool behavior
- Add new configuration options
- Fix important bugs
- Add security features

Files to update:
- `README.md` - User-facing documentation
- `CLAUDE.md` - Developer context for AI assistants
- `CHANGELOG.md` - Version history (follow Keep a Changelog format)
- `SECURITY.md` - Security policies and features (if security-related)
- Tool docstrings in the tool file

## Questions?

Open an issue with the "question" label if you need help or clarification.

---

Thank you for contributing!
