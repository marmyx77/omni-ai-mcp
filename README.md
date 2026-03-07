# omni-ai-mcp

**The complete AI bridge for Claude Code** — Gemini's exclusive capabilities (video, TTS, 1M context, RAG, Deep Research) plus 400+ models via OpenRouter. One MCP server, every AI model, zero friction.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Version 4.0.1](https://img.shields.io/badge/version-4.0.1-green.svg)](https://github.com/marmyx77/omni-ai-mcp/releases)
[![PyPI](https://img.shields.io/badge/PyPI-omni--ai--mcp-blue.svg)](https://pypi.org/project/omni-ai-mcp/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

---

## Why This Exists

Claude is exceptional at reasoning and code generation. But sometimes you need more:

- A **second opinion** from a different AI model (GPT-4o, Llama, Mistral, Claude via OpenRouter)
- **Real-time web search** with Google grounding and source citations
- **Autonomous deep research** that runs for minutes and produces structured reports from 40+ sources
- **Video generation** with Veo 3.1 — the only MCP server with native audio video generation
- **Image generation** with Imagen up to 4K resolution
- **Text-to-speech** with 30 natural voices and multi-speaker support
- **RAG** for querying your own documents with citations
- **Large codebase analysis** with Gemini's 1M token context window
- **Multi-turn conversations** with cloud persistence (55-day retention, resume from any device)
- Access to **400+ models** through one unified interface

omni-ai-mcp bridges Claude Code with Google Gemini and OpenRouter, enabling Claude to orchestrate any AI model as a tool.

---

## What's New in v4.0.0–4.0.1

### Multi-Provider: Gemini + OpenRouter

```python
# Ask any of 400+ models — auto-routes from model name
ask_model("Explain quantum computing", model="openai/gpt-4o")
ask_model("Write a poem", model="meta-llama/llama-3.3-70b-instruct")
ask_model("Review this code", model="gemini-3.1-pro-preview")  # auto-routes to Gemini native API

# If no Gemini key but OpenRouter key exists, Gemini models route via OpenRouter automatically
ask_model("Summarize this", model="gemini-3-flash-preview")  # -> google/ prefix on OpenRouter

# Discover all available models
gemini_list_models()
```

### Dynamic Model Registry

No more hardcoded model IDs. The server discovers available models at runtime and always uses the latest. If a model is deprecated, it automatically falls back to the next available option.

```bash
# Override via env vars if needed:
export GEMINI_MODEL_PRO=gemini-3.1-pro-preview
export OPENROUTER_DEFAULT_MODEL=openai/gpt-4o
```

### Smart Routing Rules

1. Explicit Gemini model + `GEMINI_API_KEY` -> **always** Gemini native API (fastest, cheapest)
2. Gemini model + no Gemini key + `OPENROUTER_API_KEY` -> OpenRouter `google/` prefix (automatic fallback)
3. `veo-*`, `imagen-*`, `deep-research-*` models -> Gemini native only (no OpenRouter equivalent)
4. OpenRouter model (`openai/`, `meta-llama/`, etc.) -> OpenRouter (requires `OPENROUTER_API_KEY`)

### PyPI Distribution

```bash
pip install omni-ai-mcp
omni-ai-mcp-setup  # interactive setup wizard
```

---

## 20 Tools

### Multi-Provider
| Tool | Description |
|------|-------------|
| `ask_model` | Ask any AI: Gemini or 400+ models via OpenRouter — auto-routes from model name |
| `gemini_list_models` | Live model discovery: Gemini registry + OpenRouter catalog, deprecation warnings |

### Text & Reasoning
| Tool | Description | Model |
|------|-------------|-------|
| `ask_gemini` | Text generation with thinking mode, multi-turn, dual storage (local/cloud) | Gemini 3.1 Pro |
| `gemini_code_review` | Security, performance, and quality analysis | Gemini 3.1 Pro |
| `gemini_brainstorm` | Creative ideation with 6 methodologies (SCAMPER, TRIZ, etc.) | Gemini 3.1 Pro |
| `gemini_challenge` | Devil's advocate — find flaws in ideas, plans, and code | Gemini 3.1 Pro |

### Code
| Tool | Description | Model |
|------|-------------|-------|
| `gemini_analyze_codebase` | Whole-codebase analysis up to 1M tokens / 5MB | Gemini 3.1 Pro |
| `gemini_generate_code` | Structured code generation with dry-run preview and XML output | Gemini 3.1 Pro |

### Research & Web
| Tool | Description | Model |
|------|-------------|-------|
| `gemini_web_search` | Real-time search with Google grounding & citations | Gemini 3 Flash |
| `gemini_deep_research` | Autonomous 5-60 min research, 40+ sources, structured report | Deep Research Agent |

### RAG
| Tool | Description |
|------|-------------|
| `gemini_file_search` | Query documents with citations |
| `gemini_create_file_store` | Create document stores |
| `gemini_upload_file` | Upload PDF, DOCX, code, etc. |
| `gemini_list_file_stores` | List available stores |

### Media (Gemini exclusive)
| Tool | Description | Model |
|------|-------------|-------|
| `gemini_analyze_image` | Vision: describe, OCR, Q&A on images | Gemini 3 Flash |
| `gemini_generate_image` | Imagen — up to 4K resolution | Gemini 3 Pro Image |
| `gemini_generate_video` | Veo 3.1 — 4-8s with native audio (dialogue, effects, ambient) | Veo 3.1 |
| `gemini_text_to_speech` | 30 natural voices, multi-speaker dialogue | Gemini 2.5 Flash TTS |

### Conversation
| Tool | Description |
|------|-------------|
| `gemini_list_conversations` | List history: title, mode, turns, last activity |
| `gemini_delete_conversation` | Delete by ID or title (partial match) |

---

## Quick Start

### Prerequisites

- Python 3.9+
- Claude Code CLI
- Gemini API key — [get one free](https://aistudio.google.com/apikey)
- *(Optional)* OpenRouter API key — [openrouter.ai](https://openrouter.ai) for 400+ models

### Install from PyPI (Recommended)

```bash
pip install omni-ai-mcp
omni-ai-mcp-setup
```

The setup wizard configures Claude Code automatically.

### Install from Source

```bash
git clone https://github.com/marmyx77/omni-ai-mcp.git
cd omni-ai-mcp

# Gemini only
./setup.sh YOUR_GEMINI_API_KEY

# Gemini + OpenRouter (400+ models)
./setup.sh YOUR_GEMINI_API_KEY YOUR_OPENROUTER_KEY
```

Restart Claude Code. Verify:

```bash
claude mcp list
# omni-ai-mcp: Connected
```

### Manual Install

```bash
pip install 'mcp[cli]>=1.0.0' 'google-genai>=1.55.0' pydantic defusedxml filelock

mkdir -p ~/.claude-mcp-servers/omni-ai-mcp
cp -r app/ run.py pyproject.toml ~/.claude-mcp-servers/omni-ai-mcp/

claude mcp add omni-ai-mcp --scope user \
  -e GEMINI_API_KEY=YOUR_KEY \
  -e OPENROUTER_API_KEY=YOUR_OR_KEY \
  -- python3 ~/.claude-mcp-servers/omni-ai-mcp/run.py
```

---

## Usage Examples

### Multi-Model AI Orchestration

```
"Ask GPT-4o to review this authentication function"
-> ask_model(model="openai/gpt-4o", prompt="review this auth function...")

"Compare how Gemini and Llama respond to this design question"
-> ask_model(model="gemini-3.1-pro-preview", ...)
-> ask_model(model="meta-llama/llama-3.3-70b-instruct", ...)

"Get a Mistral opinion on this French legal document"
-> ask_model(model="mistralai/mistral-large-2512", ...)
```

### Conversations with Memory

Gemini remembers previous context across calls via `continuation_id`:

```
# First turn
"Ask Gemini to analyze @src/auth.py for security issues"
# Returns: continuation_id: abc-123

# Follow-up — Gemini remembers the previous analysis
"Ask Gemini (continuation_id: abc-123) how to fix the SQL injection"
```

### Dual Storage Mode

| Mode | Storage | Retention | Use |
|------|---------|-----------|-----|
| `local` (default) | SQLite | 3h (configurable) | Development, quick chats |
| `cloud` | Google Interactions API | 55 days | Long projects, cross-device |

```
# Start a named cloud conversation
"Ask Gemini (mode=cloud, title='Architecture Review'): Analyze my microservices design"
# Returns: continuation_id: int_v1_abc123...

# Resume from any device within 55 days
"Ask Gemini (continuation_id: int_v1_abc123...): What about the database layer?"
```

### Deep Research

Autonomous research agent that runs 5-60 minutes:

```
"Deep research: Compare AI agent frameworks in 2025 — LangGraph, AutoGen, CrewAI"
```

The agent will:
1. Plan a comprehensive research strategy
2. Execute multiple targeted web searches
3. Synthesize findings from 40+ sources
4. Produce a structured report with citations

Use cases: market research, competitive analysis, technical deep dives, trend analysis, literature reviews.

### Codebase Analysis

Leverage Gemini's 1M token context to analyze entire codebases at once:

```
"Analyze codebase src/**/*.py with focus on security"
"Analyze codebase ['app/', 'tests/'] — find architecture issues"
```

Analysis types: `architecture`, `security`, `refactoring`, `documentation`, `dependencies`, `general`

### @File References

Include file contents directly in prompts:

```
"Ask Gemini to review @src/auth.py for security issues"
"Brainstorm improvements for @README.md"
"Code review @*.py with focus on performance"
"Analyze codebase @src/**/*.ts"
```

Supported patterns: `@file.py`, `@src/main.py`, `@*.py`, `@src/**/*.ts`, `@.` (directory listing)

### Video Generation

```
"Generate a video of ocean waves at sunset, seagulls flying, sound of waves and wind"
```

- Duration: 4-8 seconds
- Resolution: 720p or 1080p (1080p requires 8s)
- Native audio: dialogue, sound effects, ambient sounds
- For dialogue: use quotes ("Hello," she said)
- For sounds: describe explicitly (engine roaring, birds chirping)

### Image Generation

```
"Generate an image of a futuristic Tokyo street at night, neon lights reflecting on wet pavement,
cinematic, shot on 35mm lens"
```

- Resolution: up to 4K with Pro model
- Aspect ratios: 1:1, 16:9, 9:16, 3:2, 4:5, and more
- Use descriptive sentences, not keyword lists

### Text-to-Speech

```
"Convert this article to speech using the Charon voice (informative, neutral)"
```

30 available voices — Bright: Zephyr, Autonoe / Upbeat: Puck, Laomedeia / Informative: Charon, Rasalgethi / Warm: Sulafat, Vindemiatrix / and 22 more.

Multi-speaker dialogue:

```python
gemini_text_to_speech(
    text="Host: Welcome!\nGuest: Thanks for having me!",
    speakers=[
        {"name": "Host", "voice": "Charon"},
        {"name": "Guest", "voice": "Aoede"}
    ]
)
```

### Image Analysis

```
"Analyze this screenshot and extract all visible text: @screenshot.png"
"Describe what's in this diagram and explain the architecture: @diagram.png"
```

Supported formats: PNG, JPG, JPEG, GIF, WEBP

### RAG (Document Search)

```
# 1. Create a store
"Create a Gemini file store called 'project-docs'"

# 2. Upload files
"Upload the API specification PDF to the project-docs store"

# 3. Query
"Search the project-docs store: What are the rate limits?"
```

### Challenge Tool

Get critical analysis before implementing — find flaws early:

```
"Challenge this plan with focus on security:
We'll store user sessions in localStorage and use MD5 for passwords"
```

The tool acts as a Devil's Advocate — it will NOT agree with you.
Focus areas: `general`, `security`, `performance`, `maintainability`, `scalability`, `cost`

### Code Generation

```
"Generate a Python FastAPI endpoint for JWT authentication with refresh tokens"
```

Output is structured XML that Claude can apply directly:

```xml
<GENERATED_CODE>
<FILE action="create" path="src/auth.py">
# Complete implementation here...
</FILE>
</GENERATED_CODE>
```

Options: `dry_run=true` to preview without writing, `language`, `style` (production/prototype/minimal), `output_dir`

### Thinking Mode

```
"Ask Gemini with high thinking level:
Design an optimal database schema for a social media platform at scale"
```

Levels: `off` (default), `low` (fast reasoning), `high` (deep analysis)

---

## Model Selection

### Text Models

| Alias | Resolved Model | Best For |
|-------|----------------|----------|
| `pro` | `gemini-3.1-pro-preview` | Complex reasoning, coding, analysis |
| `flash` | `gemini-3-flash-preview` | Balanced speed/quality |
| `fast` / `flash-lite` | `gemini-3.1-flash-lite-preview` | High-volume, simple tasks |

Models are resolved dynamically at runtime — if a model is deprecated, the registry automatically falls back to the next available option.

### OpenRouter Models (via `ask_model`)

| Provider | Example Model ID | Notes |
|----------|-----------------|-------|
| OpenAI | `openai/gpt-4o` | GPT-4o, o3, o4-mini |
| Meta | `meta-llama/llama-3.3-70b-instruct` | Open source, fast |
| Anthropic | `anthropic/claude-3.5-sonnet` | Claude via OpenRouter |
| Mistral | `mistralai/mistral-large-2512` | Strong on EU languages |
| Google | `google/gemini-3.1-pro-preview` | Gemini via OpenRouter (fallback) |
| 340+ more | — | `gemini_list_models()` to browse |

---

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | **required** | Google Gemini API key |
| `OPENROUTER_API_KEY` | — | OpenRouter key (enables `ask_model` for 400+ models) |
| `GEMINI_MODEL_PRO` | `gemini-3.1-pro-preview` | Override Pro text model |
| `GEMINI_MODEL_FLASH` | `gemini-2.5-flash` | Static fallback model |
| `GEMINI_MODEL_DEEP_RESEARCH` | `deep-research-pro-preview` | Override research agent |
| `OPENROUTER_DEFAULT_MODEL` | `openai/gpt-4o` | Default OpenRouter model |
| `GEMINI_SANDBOX_ROOT` | cwd | Root directory for file access |
| `GEMINI_SANDBOX_ENABLED` | `true` | Enable path sandboxing |
| `GEMINI_MAX_FILE_SIZE` | `102400` | Max file size in bytes (100KB) |
| `GEMINI_CONVERSATION_TTL_HOURS` | `3` | Local conversation expiry |
| `GEMINI_CONVERSATION_MAX_TURNS` | `50` | Max turns per thread |
| `GEMINI_LOG_DIR` | `~/.omni-ai-mcp` | Log & DB directory |
| `GEMINI_LOG_FORMAT` | `text` | `json` or `text` |
| `GEMINI_DISABLED_TOOLS` | — | Comma-separated tool names to disable |

---

## Claude Code Plugin

### Slash Commands

Included in `.claude/commands/` (auto-available in Claude Code):

| Command | Action |
|---------|--------|
| `/gemini <prompt>` | Quick ask_gemini call |
| `/gemini-research <topic>` | Start deep research |
| `/gemini-review <file>` | Code review |
| `/gemini-models` | List available models |
| `/ask-model [model] <prompt>` | Ask any model (GPT-4o, Llama, Gemini, etc.) |

### Subagents

Included in `.claude/agents/` — Claude Code invokes these automatically:

| Agent | Trigger | Capability |
|-------|---------|------------|
| `gemini-researcher` | "research X", "find out about Y" | Deep Research Agent, 40+ sources |
| `gemini-analyzer` | "analyze codebase", "security audit" | 1M token context window |
| `model-orchestrator` | "ask GPT-4o", "compare models", "use Llama" | Routes to 400+ models |

---

## Multi-Model Architecture

omni-ai-mcp uses **Claude as the orchestrator** with other models as tools:

```
User -> Claude Code
            (orchestrates)
       omni-ai-mcp tools
       +-- ask_model("openai/gpt-4o")       -> OpenRouter -> GPT-4o
       +-- ask_model("meta-llama/...")       -> OpenRouter -> Llama 3
       +-- ask_model("gemini-3.1-pro...")    -> Gemini API (native)
       +-- ask_gemini(...)                   -> Gemini API -> Gemini Pro
       +-- gemini_deep_research(...)         -> Gemini API -> Deep Research Agent
       +-- gemini_generate_video(...)        -> Gemini API -> Veo 3.1
```

This is different from **provider replacement** tools like [claude-code-router](https://github.com/musistudio/claude-code-router) which replace Claude's backend entirely. omni-ai-mcp keeps Claude in control while giving it access to every AI model as a tool.

---

## Architecture

```
omni-ai-mcp/
+-- app/
|   +-- server.py              # FastMCP -- 20 @mcp.tool() registrations
|   +-- core/                  # Config, structured logging, security
|   +-- services/
|   |   +-- gemini.py          # Gemini client + generate_with_fallback()
|   |   +-- model_registry.py  # Dynamic model discovery (API + cache)
|   |   +-- openrouter.py      # OpenRouter client (OpenAI-compatible)
|   |   +-- persistence.py     # SQLite conversation storage + index
|   +-- tools/                 # Tool implementations by domain
|   |   +-- text/              # ask_gemini, ask_model, models, brainstorm, etc.
|   |   +-- code/              # analyze_codebase, generate_code
|   |   +-- media/             # image, video, TTS
|   |   +-- web/               # web_search, deep_research
|   |   +-- rag/               # file_store, file_search, upload
|   +-- schemas/               # Pydantic v2 validation
|   +-- utils/                 # @file expansion, token estimation
+-- tests/                     # 174+ tests (unit + integration)
+-- .claude/
|   +-- commands/              # Slash commands
|   +-- agents/                # Subagents
+-- setup.sh                   # One-command install
+-- manifest.json              # .mcpb bundle manifest
+-- pyproject.toml
```

---

## Security

- **Path sandboxing**: all file access restricted to `GEMINI_SANDBOX_ROOT`
- **Secrets sanitization**: API keys masked in logs (Google, AWS, GitHub, OpenAI, Anthropic, Slack, JWT, Bearer tokens)
- **XML sanitization**: LLM output sanitized before parsing to prevent injection
- **Atomic file writes**: automatic backups before any file modification
- **Input validation**: Pydantic v2 schemas at all tool boundaries
- **Rate limiting**: via provider-side quotas

---

## Docker Deployment

```bash
# Build and run
docker-compose up -d

# With log viewer (port 8080)
docker-compose --profile monitoring up -d
```

Docker features: non-root user, read-only filesystem with tmpfs, health check every 30s, resource limits (2 CPU, 2GB RAM), log rotation.

---

## Troubleshooting

### MCP not connecting

```bash
claude mcp list           # check registration
claude mcp remove omni-ai-mcp
./setup.sh YOUR_API_KEY   # re-register
# Restart Claude Code
```

### Import or syntax errors

```bash
python3 -c "from app.core.config import config; print(f'v{config.version}')"
python3 -m pytest tests/unit/ -q
```

### Video / Image generation timeouts

- Video generation can take 1-6 minutes — this is normal
- Large images (4K) take longer
- Check your Gemini API quota at [AI Studio](https://aistudio.google.com/)

### OpenRouter errors

- Verify `OPENROUTER_API_KEY` is set and has credit
- Check the model ID with `gemini_list_models(include_openrouter=True)`
- Use the exact model ID from the list

### API key update

```bash
claude mcp remove omni-ai-mcp
claude mcp add omni-ai-mcp --scope user \
  -e GEMINI_API_KEY=NEW_KEY \
  -e OPENROUTER_API_KEY=NEW_OR_KEY \
  -- python3 ~/.claude-mcp-servers/omni-ai-mcp/run.py
```

---

## API Costs

| Feature | Notes |
|---------|-------|
| Text generation | Free tier available · $0.075-0.30 per 1M tokens |
| Web Search | ~$14 per 1000 queries |
| File Search indexing | $0.15 per 1M tokens (one-time) |
| Image generation | Varies by resolution and model |
| Video generation | Varies by duration/resolution |
| Text-to-speech | Varies by character count |
| OpenRouter | Per-model pricing — see [openrouter.ai/models](https://openrouter.ai/models) |

See [Google AI pricing](https://ai.google.dev/pricing) for Gemini rates.

---

## Development

```bash
# Run tests
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v  # requires GEMINI_API_KEY

# Quick import check
python -c "from app.core.config import config; print(f'v{config.version}')"

# Reinstall after changes
rsync -a app/ ~/.claude-mcp-servers/omni-ai-mcp/app/
# Restart Claude Code
```

### Adding a New Tool

1. Create `app/tools/<domain>/my_tool.py` with `@tool(name="...", description="...", input_schema=...)`
2. Import in `app/tools/<domain>/__init__.py`
3. Add Pydantic schema in `app/schemas/inputs.py`
4. Write tests in `tests/unit/`

See [CLAUDE.md](CLAUDE.md) for the full development guide.

---

## Changelog

### v4.0.1
- Fixed routing: Gemini models always use native API when key available (even if `provider=openrouter`)
- Added OpenRouter fallback for Gemini text models when no Gemini key (`google/` prefix)
- Fixed Python 3.11 f-string syntax in challenge tool
- Fixed stale unit test imports (103 -> 174 passing tests)
- Fixed model registry: corrected flash model names (`gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`)

### v4.0.0
- `ask_model`: 400+ models via OpenRouter — auto-routes from model name
- `gemini_list_models`: live model discovery with deprecation warnings
- Dynamic model registry: no more hardcoded model IDs
- PyPI distribution: `pip install omni-ai-mcp`
- Claude Code plugin: slash commands + subagents
- GitHub Actions CI/CD with Trusted Publishing

### v3.3.0
- Dual storage mode for `ask_gemini`: local (SQLite) or cloud (Interactions API, 55-day retention)
- `gemini_list_conversations`, `gemini_delete_conversation`
- Cross-platform file locking

### v3.2.0
- `gemini_deep_research`: autonomous multi-step research (5-60 min, 40+ sources)

### v3.0.0
- FastMCP migration, SQLite persistence, security hardening

---

## Contributing

Contributions are welcome! Open an issue or pull request on [GitHub](https://github.com/marmyx77/omni-ai-mcp).

---

## License

MIT — see [LICENSE](LICENSE)
