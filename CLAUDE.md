# CLAUDE.md

This file provides context to Claude Code when working with this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that bridges Claude Code with Google Gemini AI. It enables AI collaboration by allowing Claude to access Gemini's capabilities including text generation with thinking mode, web search, RAG, image analysis, image generation, video generation, and text-to-speech.

**Version:** 4.0.0
**SDK:** google-genai >= 1.55.0 (Interactions API) + FastMCP + filelock
**Architecture:** Modular package structure with SQLite persistence and conversation index

## Architecture (v3.3.0)

**Production-grade MCP server** with FastMCP SDK:

```
omni-ai-mcp/
├── run.py                    # Entry point wrapper
├── pyproject.toml            # Package configuration
├── app/
│   ├── __init__.py          # Package init, exports main(), __version__
│   ├── server.py            # FastMCP server (18 tools with @mcp.tool())
│   │
│   ├── core/                # Infrastructure & cross-cutting concerns
│   │   ├── __init__.py      # Core exports
│   │   ├── config.py        # Configuration (env vars, defaults, version, model IDs)
│   │   ├── logging.py       # StructuredLogger, activity logging, JSON format
│   │   └── security.py      # PathValidator, SecretsSanitizer, SafeFileWriter, cross-platform file locking
│   │
│   ├── services/            # External service integrations
│   │   ├── __init__.py      # Service exports
│   │   ├── gemini.py        # Gemini client wrapper, generate_with_fallback()
│   │   └── persistence.py   # SQLite conversation storage + conversation index
│   │
│   ├── tools/               # MCP tool implementations (by domain)
│   │   ├── __init__.py      # Tool registration, get_tools_list()
│   │   ├── registry.py      # ToolRegistry with @tool decorator
│   │   ├── text/            # Text/reasoning tools
│   │   │   ├── ask_gemini.py    # Text generation with thinking + dual mode
│   │   │   ├── brainstorm.py    # Creative ideation (6 methodologies)
│   │   │   ├── challenge.py     # Critical thinking / Devil's Advocate
│   │   │   ├── code_review.py   # Code analysis
│   │   │   └── conversations.py # Conversation management (list, delete)
│   │   ├── code/            # Code tools
│   │   │   ├── analyze_codebase.py # Large-scale analysis (1M context, 5MB limit)
│   │   │   └── generate_code.py    # Structured generation with dry-run & XML sanitization
│   │   ├── media/           # Media tools
│   │   │   ├── analyze_image.py  # Vision analysis
│   │   │   ├── generate_image.py # Imagen image generation
│   │   │   ├── generate_video.py # Veo video generation
│   │   │   └── text_to_speech.py # TTS with 30 voices
│   │   ├── web/             # Web tools
│   │   │   ├── web_search.py     # Google-grounded search
│   │   │   └── deep_research.py  # Deep Research Agent (Interactions API)
│   │   └── rag/             # RAG tools
│   │       ├── file_store.py    # Create/list file stores
│   │       ├── file_search.py   # Query documents
│   │       └── upload.py        # Upload to stores
│   │
│   ├── utils/               # Helper functions
│   │   ├── __init__.py
│   │   ├── file_refs.py     # @file expansion, expand_file_references()
│   │   └── tokens.py        # Token estimation, size limits
│   │
│   ├── schemas/             # Pydantic v2 validation
│   │   ├── __init__.py
│   │   └── inputs.py        # Tool input schemas (7 validated tools)
│   │
│   └── middleware/          # Request processing
│       └── __init__.py
│
└── tests/                   # Test suite (118+ tests)
    ├── conftest.py          # Pytest fixtures
    ├── unit/                # Unit tests
    └── integration/         # Integration tests
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Entry Point | `run.py` | Wrapper that imports and runs `app.main()` |
| FastMCP Server | `app/server.py` | FastMCP server with 18 `@mcp.tool()` registrations |
| Config | `app/core/config.py` | Environment variables, defaults, version, model IDs |
| Logging | `app/core/logging.py` | StructuredLogger with JSON support |
| Security | `app/core/security.py` | Sandboxing, sanitization, safe writes, cross-platform file locking |
| Tool Registry | `app/tools/registry.py` | @tool decorator, tool discovery |
| Gemini Client | `app/services/gemini.py` | API wrapper with generate_with_fallback() |
| Persistence | `app/services/persistence.py` | SQLite conversation storage + conversation index |

### Available Tools (18)

| Tool | Description | Default Model |
|------|-------------|---------------|
| `ask_gemini` | Text generation with thinking + dual mode (local/cloud) | Gemini 3 Pro |
| `gemini_code_review` | Code analysis | Gemini 3 Pro |
| `gemini_brainstorm` | Advanced brainstorming (6 methodologies) | Gemini 3 Pro |
| `gemini_challenge` | Critical thinking / Devil's Advocate | Gemini 3 Pro |
| `gemini_web_search` | Google-grounded search | Gemini 2.5 Flash |
| `gemini_deep_research` | Autonomous multi-step research (5-60 min) | Deep Research Agent |
| `gemini_list_conversations` | **NEW** List conversations with title, mode, activity | - |
| `gemini_delete_conversation` | **NEW** Delete conversations by ID or title | - |
| `gemini_file_search` | RAG document queries | Gemini 2.5 Flash |
| `gemini_create_file_store` | Create RAG stores | - |
| `gemini_upload_file` | Upload to RAG stores | - |
| `gemini_list_file_stores` | List RAG stores | - |
| `gemini_analyze_image` | Image analysis (vision) | Gemini 2.5 Flash |
| `gemini_generate_image` | Image generation | Gemini 3 Pro Image |
| `gemini_generate_video` | Video generation (sync polling) | Veo 3.1 |
| `gemini_text_to_speech` | TTS with 30 voices | Gemini 2.5 Flash TTS |
| `gemini_analyze_codebase` | Large codebase analysis (1M context, 5MB limit) | Gemini 3 Pro |
| `gemini_generate_code` | Structured code generation (dry-run, XML sanitization) | Gemini 3 Pro |


## Development Commands

### Run server locally for testing
```bash
GEMINI_API_KEY=your_key python3 run.py
```

### Test JSON-RPC manually
```bash
# Initialize
echo '{"jsonrpc":"2.0","method":"initialize","id":1}' | GEMINI_API_KEY=your_key python3 run.py

# List tools
echo '{"jsonrpc":"2.0","method":"tools/list","id":2}' | GEMINI_API_KEY=your_key python3 run.py
```

### Install to Claude Code
```bash
./setup.sh YOUR_API_KEY
```

### Reinstall after changes
```bash
cp -r app/ ~/.claude-mcp-servers/omni-ai-mcp/
cp run.py ~/.claude-mcp-servers/omni-ai-mcp/
# Then restart Claude Code
```

### Run tests
```bash
# Quick verification (no pytest needed)
python3 -c "
from app.core.config import config
from app.tools.code.generate_code import parse_generated_code, sanitize_xml_content
print(f'Version: {config.version}')
print('All imports OK')
"

# Full test suite (requires pytest)
python3 -m pytest tests/unit/ -v
```

## Code Style

- **Python 3.9+** required (FastMCP SDK requirement)
- Type hints for function signatures
- Docstrings for public functions (Google style)
- Keep tool implementations self-contained
- Error handling returns user-friendly messages
- Use Pydantic for input validation

## Adding a New Tool

### Step 1: Create the tool file

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
    description="What the tool does",
    input_schema=MY_TOOL_SCHEMA,
    tags=["category"]
)
def my_tool(param: str, optional: str = "default") -> str:
    """
    Tool implementation docstring.

    Args:
        param: Required parameter description
        optional: Optional parameter description

    Returns:
        Result string
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

### Step 2: Register in tools/domain/__init__.py

```python
# app/tools/domain/__init__.py
from . import my_tool
```

### Step 3: Add Pydantic schema (recommended)

```python
# app/schemas/inputs.py

class MyToolInput(BaseModel):
    param: str = Field(..., min_length=1)
    optional: str = Field(default="default")
```

## Key Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | Required | Google Gemini API key |
| `GEMINI_SANDBOX_ROOT` | cwd | Root directory for file access |
| `GEMINI_SANDBOX_ENABLED` | true | Enable path sandboxing |
| `GEMINI_MAX_FILE_SIZE` | 102400 | Max file size in bytes (100KB) |
| `GEMINI_ACTIVITY_LOG` | true | Enable activity logging |
| `GEMINI_LOG_DIR` | ~/.omni-ai-mcp | Log directory |
| `GEMINI_LOG_FORMAT` | text | "json" or "text" |
| `GEMINI_CONVERSATION_TTL_HOURS` | 3 | Thread expiration |
| `GEMINI_CONVERSATION_MAX_TURNS` | 50 | Max turns per thread |
| `GEMINI_DISABLED_TOOLS` | - | Comma-separated tool names to disable |
| `GEMINI_MODEL_PRO` | gemini-3-pro-preview | Text model (Pro) |
| `GEMINI_MODEL_FLASH` | gemini-2.5-flash | Text model (Flash) |
| `GEMINI_MODEL_IMAGE_PRO` | gemini-3-pro-image-preview | Image model (Pro) |
| `GEMINI_MODEL_VEO31` | veo-3.1-generate-preview | Video model (Veo 3.1) |
| `GEMINI_MODEL_TTS_FLASH` | gemini-2.5-flash-preview-tts | TTS model (Flash) |

## Security Features (v3.0.1)

### Path Sandboxing
```python
from app.core.security import validate_path, secure_read_file

# Validates path is within sandbox, blocks traversal attacks
safe_path = validate_path(user_input)
content = secure_read_file(file_path)
```

### Safe File Writing
```python
from app.core.security import SafeFileWriter, secure_write_file

# Atomic writes with automatic backup
result = secure_write_file("/path/to/file.py", "content")
# Creates backup at .gemini_backups/path/to/file.py.TIMESTAMP.bak
```

### Secrets Sanitization
```python
from app.core.security import secrets_sanitizer

# Detects and masks sensitive data
safe_text = secrets_sanitizer.sanitize("API key: AIzaSyB...")
# Returns: "API key: [REDACTED_GOOGLE_API_KEY]"
```

### XML Sanitization (v3.0.1)
```python
from app.tools.code.generate_code import sanitize_xml_content, parse_generated_code

# Sanitizes XML before parsing to prevent injection
clean_xml = sanitize_xml_content(raw_output)
files = parse_generated_code(clean_xml)
# Validates action types, blocks path traversal in generated paths
```

### Detected Secret Patterns
- Google API keys (AIza...)
- AWS keys (AKIA...)
- GitHub tokens (ghp_, gho_, ghs_, ghr_, ghu_)
- JWT tokens
- Bearer tokens
- Private keys (PEM format)
- URL passwords
- Anthropic API keys (sk-ant-...)
- OpenAI API keys (sk-...)
- Slack tokens (xox...)

## Input Validation

Pydantic v2 schemas for type-safe validation:

```python
from app.schemas.inputs import validate_tool_input

# Validates and applies defaults
args = validate_tool_input("ask_gemini", {
    "prompt": "Hello",
    "temperature": 0.9
})

# Raises ValueError for invalid input
validate_tool_input("ask_gemini", {"prompt": "", "temperature": 2.0})
# ValueError: temperature must be <= 1.0
```

### Validated Tools
- `ask_gemini` - prompt, model, temperature, thinking_level
- `gemini_generate_code` - prompt, context_files, language, style, dry_run
- `gemini_challenge` - statement, context, focus
- `gemini_analyze_codebase` - prompt, files, analysis_type
- `gemini_code_review` - code, focus, model
- `gemini_brainstorm` - topic, methodology, idea_count
- `gemini_deep_research` - query, max_wait_minutes, continuation_id

## Interactions API Integration (v3.2.0 + v3.3.0)

The server integrates with Google's **Interactions API** for cloud-based features:

### Available Modes

| Tool | API | Mode | Use Case |
|------|-----|------|----------|
| `gemini_deep_research` | Interactions API | Background (5-60 min) | Autonomous multi-step research |
| `ask_gemini` | Interactions API | Synchronous (`mode="cloud"`) | Cloud-persisted conversations |
| `ask_gemini` | SQLite | Local (`mode="local"`) | Fast local conversations |

### Cloud Mode (ask_gemini)

```python
# Start cloud conversation
result = ask_gemini(
    prompt="Analyze this architecture",
    mode="cloud",
    title="Architecture Review"
)
# Returns: continuation_id: int_v1_abc123...

# Resume from any device (55-day retention)
result = ask_gemini(
    prompt="What about security?",
    continuation_id="int_v1_abc123..."
)
```

### Deep Research

```python
# Start autonomous research (runs 5-60 minutes)
result = gemini_deep_research(
    query="Compare React vs Vue for enterprise apps",
    max_wait_minutes=30
)

# Follow up on results
result = gemini_deep_research(
    query="Focus on performance benchmarks",
    continuation_id="int_abc123..."
)
```

### API Documentation
- Official docs: https://ai.google.dev/gemini-api/docs/interactions
- `model` parameter: Standard queries (sync, no background)
- `agent` parameter: Agent workflows (requires `background=true`)

## Conversation Memory

Multi-turn conversations using `continuation_id` with **dual storage**:

### Local Mode (SQLite - Default)
```python
from app.services.persistence import conversation_memory

# Get or create thread
thread_id, is_new, thread = conversation_memory.get_or_create_thread(continuation_id)

# Build context from history
if not is_new:
    context = conversation_memory.build_context(thread_id)
    full_prompt = f"{context}\n\n{prompt}"

# Add turns
conversation_memory.add_turn(thread_id, "user", prompt, "tool_name", files)
conversation_memory.add_turn(thread_id, "assistant", response, "tool_name", [])

# Return with continuation_id
return f"{response}\n\n---\n*continuation_id: {thread_id}*"
```

### Cloud Mode (Interactions API)
```python
from app.services import client

# Create interaction with model (not agent!)
interaction = client.interactions.create(
    model="gemini-2.5-flash",  # Use model for sync queries
    input=prompt,
    previous_interaction_id=continuation_id  # For follow-ups
)

# Response is immediate (no polling needed)
response_text = interaction.outputs[-1].text
thread_id = f"int_{interaction.id}"  # Cloud IDs prefixed with int_
```

### Storage Comparison

| Feature | Local (SQLite) | Cloud (Interactions API) |
|---------|---------------|--------------------------|
| Storage | `~/.omni-ai-mcp/conversations.db` | Google servers |
| Retention | Configurable TTL (default 3h) | 55 days (paid tier) |
| Cross-device | No | Yes |
| Speed | Faster | Slightly slower |
| ID prefix | UUID | `int_` |

## @File References

Tools support @ syntax to include file contents:

- `@file.py` - Single file with line numbers
- `@src/main.py` - Path with directories
- `@*.py` - Glob patterns (max 10 files)
- `@src/**/*.ts` - Recursive glob
- `@.` - Current directory listing

```python
from app.utils.file_refs import expand_file_references

expanded = expand_file_references("Review @src/main.py")
# Includes file content with line numbers
```

### Line Numbers Format
```
  1│ #!/usr/bin/env python3
  2│ def hello():
  3│     print("Hello")
```

Skipped for non-code files: `.json`, `.md`, `.txt`, `.csv`

## New Features (v3.0.1)

### Dry-Run Mode for Code Generation
```python
# Preview generated code without saving
result = generate_code(
    prompt="Create a login form",
    dry_run=True  # Shows preview, no files written
)
```

### Async Video Polling
Video generation now uses async polling when running in an async context:
```python
# Automatically uses asyncio.to_thread for non-blocking polling
# Falls back to sync polling if no event loop
```

### Total Byte Limit for Codebase Analysis
```python
# analyze_codebase now enforces 5MB total limit
# Prevents memory exhaustion DoS attacks
```

## Logging

### Structured JSON Logging
```python
from app.core.logging import structured_logger

# Log tool events
structured_logger.tool_start("ask_gemini", "req123", {"prompt": "..."})
structured_logger.tool_success("ask_gemini", "req123", 1500.5, 2048)
structured_logger.tool_error("ask_gemini", "req123", 500.0, "API error")
```

### JSON Output Format
```json
{
  "timestamp": "2025-12-08T14:30:00.000Z",
  "level": "INFO",
  "tool": "ask_gemini",
  "status": "start",
  "request_id": "a1b2c3d4",
  "details": {"args_keys": ["prompt", "model"]}
}
```

### Activity Logging
```python
from app.core.logging import log_activity

log_activity("ask_gemini", "success", duration_ms=1500,
             details={"result_len": 2048})
```

## Test Suite

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run unit tests only
python3 -m pytest tests/unit/ -v

# Run integration tests
python3 -m pytest tests/integration/ -v

# Run specific test file
python3 -m pytest tests/unit/test_safe_write.py -v

# Run with coverage
python3 -m pytest tests/ --cov=app --cov-report=html
```

### Test Structure (118+ tests)
```
tests/
├── conftest.py                    # Shared fixtures (temp_sandbox, etc.)
├── unit/                          # Unit tests
│   ├── test_safe_write.py         # SafeFileWriter, atomic writes, backups
│   ├── test_parse_generated_code.py
│   ├── test_expand_file_references.py
│   ├── test_add_line_numbers.py
│   ├── test_validate_path.py      # Path traversal prevention
│   ├── test_pydantic_schemas.py   # Input validation
│   └── test_secrets_sanitizer.py  # Secret detection patterns
└── integration/                   # v3.0.0+ integration tests
    ├── test_fastmcp_server.py     # FastMCP initialization (16 tests)
    ├── test_mcp_tools.py          # Tool signatures & schemas (32 tests)
    ├── test_sqlite_persistence.py # SQLite storage (26 tests)
    ├── test_security_v3.py        # Security features (26 tests)
    └── real_outputs/              # Live MCP tool call outputs
```

## Docker Deployment

```bash
# Build and run
docker-compose up -d

# With monitoring
docker-compose --profile monitoring up -d
```

### docker-compose.yml Features
- Non-root user execution
- Health check every 30 seconds
- Read-only filesystem with tmpfs
- Resource limits (2 CPU, 2GB RAM)
- Log rotation (10MB max, 3 files)

## Gemini API Nuances

### Thinking Mode
- Gemini 3 Pro: Use `thinking_level` ("low" or "high")
- Gemini 2.5: Use `thinking_budget` (1024 for low, 8192 for high)
- Set `include_thoughts=True` to see reasoning process

### Web Search
- Uses `google_search` tool in config
- Grounding metadata contains source URLs
- Extract from `candidate.grounding_metadata.grounding_chunks`

### File Search (RAG)
- Stores persist on Google's servers
- Use `file_search_stores.create()` to make stores
- Upload with `file_search_stores.upload_to_file_search_store()`
- Query with `file_search` tool in generate_content config

### Image Generation
- Pro model supports up to 4K resolution
- Flash model limited to 1024px
- Response contains `inline_data` with image bytes

### Video Generation
- Veo 3.1 supports native audio (dialogue, effects, ambient)
- 1080p requires 8 second duration
- Uses async polling with `asyncio.to_thread()` (v3.0.1)
- Can take 1-6 minutes to generate

### Text-to-Speech
- 30 voice options with different characteristics
- Multi-speaker supports up to 2 voices
- Output is PCM 24kHz, 16-bit, mono WAV

## Security Notes

- Never commit API keys
- API key passed via environment variable
- Test files (test_*.png, test_*.mp4) are git-ignored
- Server validates API key presence before initializing
- All file operations respect sandbox boundaries
- XML output from LLM is sanitized before parsing (v3.0.1)
- Total byte limit prevents DoS in codebase analysis (v3.0.1)

## Roadmap

### v3.3.0 (Current) - Interactions API for ask_gemini
- ✅ **Dual Storage Mode**: `ask_gemini` supports local (SQLite) and cloud (Interactions API)
  - `mode="local"` (default): Fast, configurable TTL (3 hours)
  - `mode="cloud"`: 55-day server-side retention, cross-device access
  - Auto-detection from `continuation_id` prefix (`int_` = cloud)
- ✅ **Conversation Management**: New tools to list and manage conversations
  - `gemini_list_conversations`: List with title, mode (💾/☁️), activity, turn count
  - `gemini_delete_conversation`: Delete by ID or title (partial match)
- ✅ **Cross-Platform File Locking**: Using `filelock` library
- ✅ **Configurable Model Versions**: Override via environment variables
- 🔧 **Bug Fix**: Cloud mode now uses `model` param (was incorrectly using `agent`)

### v3.2.0 - Deep Research Agent (Interactions API)
- ✅ **`gemini_deep_research`**: Autonomous multi-step research (5-60 min)
- ✅ **First Interactions API Integration**: Background execution with async polling
- ✅ **Comprehensive Reports**: Synthesizes findings from 40+ sources

### v3.1.0 - Technical Debt Cleanup
- ✅ Removed 604 lines of deprecated code
- ✅ RAG short name resolution for file stores

### v4.0.0 (Future)
- Full migration to Interactions API for all tools
- Local vector store for RAG (ChromaDB/FAISS)
- Bidirectional Claude ↔ Gemini bridge via MCP
