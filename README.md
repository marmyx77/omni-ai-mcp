# omni-ai-mcp

**20 AI tools for Claude Code** — Gemini's unique capabilities (video, TTS, 1M context, RAG, Deep Research) plus 400+ models via OpenRouter. One MCP server, every AI.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Version 4.0.0](https://img.shields.io/badge/version-4.0.0-green.svg)](https://github.com/marcoarmellino/omni-ai-mcp/releases)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

---

## What's New in v4.0.0

### Multi-Provider: Gemini + OpenRouter

```bash
# Ask any model — Gemini or 400+ via OpenRouter
ask_model("Explain quantum computing", model="openai/gpt-4o")
ask_model("Write a poem", model="meta-llama/llama-3.3-70b")
ask_model("Review this code", model="gemini-3.1-pro-preview")  # auto-routes to Gemini

# Discover available models
gemini_list_models()
```

### Dynamic Model Registry

No more hardcoded model IDs. The server discovers available models at runtime and always picks the best one. If a model is deprecated, it automatically falls back.

```python
# config.py defaults are live-verified against the API on startup
# Override via env vars if needed:
export GEMINI_MODEL_PRO=gemini-3.1-pro-preview
export OPENROUTER_DEFAULT_MODEL=openai/gpt-4o
```

---

## 20 Tools

### Multi-Provider (NEW)
| Tool | Description |
|------|-------------|
| `ask_model` | Gemini or 400+ models via OpenRouter — auto-routes from model name |
| `gemini_list_models` | Live model discovery: Gemini + OpenRouter, deprecation warnings |

### Text & Reasoning
| Tool | Description | Model |
|------|-------------|-------|
| `ask_gemini` | Text generation with thinking mode, dual storage (local/cloud) | Gemini 3.1 Pro |
| `gemini_code_review` | Security, performance, quality analysis | Gemini 3.1 Pro |
| `gemini_brainstorm` | Creative ideation with 6 methodologies | Gemini 3.1 Pro |
| `gemini_challenge` | Devil's advocate — find flaws in ideas/plans/code | Gemini 3.1 Pro |

### Code
| Tool | Description | Model |
|------|-------------|-------|
| `gemini_analyze_codebase` | Whole-codebase analysis up to 1M tokens / 5MB | Gemini 3.1 Pro |
| `gemini_generate_code` | Structured code gen with dry-run preview | Gemini 3.1 Pro |

### Research & Web
| Tool | Description | Model |
|------|-------------|-------|
| `gemini_web_search` | Real-time search with Google grounding & citations | Gemini 2.5 Flash |
| `gemini_deep_research` | Autonomous 5–60 min research, 40+ sources | Deep Research Agent |

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
| `gemini_analyze_image` | Vision: describe, OCR, Q&A | Gemini 2.5 Flash |
| `gemini_generate_image` | Imagen — up to 4K | Gemini 3.1 Pro Image |
| `gemini_generate_video` | Veo 3.1 — 4-8s with native audio | Veo 3.1 |
| `gemini_text_to_speech` | 30 voices, multi-speaker | Gemini 2.5 Flash TTS |

### Conversation
| Tool | Description |
|------|-------------|
| `gemini_list_conversations` | List history: title, mode, turns, last activity |
| `gemini_delete_conversation` | Delete by ID or title |

---

## Quick Start

### Prerequisites

- Python 3.9+
- Claude Code CLI
- Gemini API key — [get one free](https://aistudio.google.com/apikey)
- *(Optional)* OpenRouter API key — [openrouter.ai](https://openrouter.ai) for 400+ models

### Install

```bash
git clone https://github.com/marcoarmellino/omni-ai-mcp.git
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
  -- python3 ~/.claude-mcp-servers/omni-ai-mcp/run.py
```

### PyPI (coming soon)

```bash
pip install omni-ai-mcp
omni-ai-mcp-setup
```

---

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | **required** | Google Gemini API key |
| `OPENROUTER_API_KEY` | — | OpenRouter key (enables `ask_model` for 400+ models) |
| `GEMINI_MODEL_PRO` | `gemini-3.1-pro-preview` | Override Pro model |
| `GEMINI_MODEL_FLASH` | `gemini-2.5-flash` | Override Flash model |
| `GEMINI_MODEL_DEEP_RESEARCH` | `deep-research-pro-preview` | Override research agent |
| `OPENROUTER_DEFAULT_MODEL` | `openai/gpt-4o` | Default OpenRouter model |
| `GEMINI_SANDBOX_ROOT` | cwd | Root for file access |
| `GEMINI_SANDBOX_ENABLED` | `true` | Enable path sandboxing |
| `GEMINI_CONVERSATION_TTL_HOURS` | `3` | Local conversation expiry |
| `GEMINI_LOG_DIR` | `~/.omni-ai-mcp` | Log & DB directory |
| `GEMINI_LOG_FORMAT` | `text` | `json` or `text` |
| `GEMINI_DISABLED_TOOLS` | — | Comma-separated tool names to disable |

---

## Examples

### Ask any model

```
ask_model("Compare Python and Go for a REST API", model="openai/gpt-4o")
ask_model("Write unit tests for this function", model="gemini-3.1-pro-preview")
ask_model("Summarize this article")  # uses default model
```

### Multi-turn conversations

```
ask_gemini("Analyze this architecture", mode="local", title="Arch Review")
# Returns: continuation_id: abc123

ask_gemini("What about security?", continuation_id="abc123")

# Cloud mode — 55-day retention, resume from any device
ask_gemini("Review my API", mode="cloud")
# Returns: continuation_id: int_abc123
```

### Deep Research

```
gemini_deep_research("Latest AI agent frameworks comparison 2025", max_wait_minutes=30)
# Runs 5-30 min, returns structured report with 40+ citations
```

### Codebase Analysis

```
gemini_analyze_codebase(
    prompt="Find security vulnerabilities",
    files=["src/**/*.py", "tests/*.py"],
    analysis_type="security"
)
```

### Video Generation

```
gemini_generate_video(
    prompt="A time-lapse of a flower blooming in a sunlit field, 4K, cinematic",
    duration=8,
    resolution="1080p"
)
```

---

## Architecture

```
omni-ai-mcp/
├── app/
│   ├── server.py              # FastMCP — 20 @mcp.tool() registrations
│   ├── core/                  # Config, logging, security
│   ├── services/
│   │   ├── gemini.py          # Gemini client + fallback logic
│   │   ├── model_registry.py  # Dynamic model discovery (NEW)
│   │   ├── openrouter.py      # OpenRouter client (NEW)
│   │   └── persistence.py     # SQLite conversation storage
│   ├── tools/                 # Tool implementations by domain
│   │   ├── text/              # ask_gemini, ask_model, models, etc.
│   │   ├── code/              # analyze_codebase, generate_code
│   │   ├── media/             # image, video, TTS
│   │   ├── web/               # web_search, deep_research
│   │   └── rag/               # file_store, file_search, upload
│   ├── schemas/               # Pydantic v2 validation
│   └── utils/                 # @file references, token estimation
├── tests/                     # 120+ tests (unit + integration)
├── .claude/
│   ├── commands/              # /gemini /gemini-research /gemini-review /gemini-models
│   └── agents/                # gemini-researcher, gemini-analyzer
├── setup.sh                   # One-command install
├── manifest.json              # .mcpb bundle manifest
└── pyproject.toml
```

---

## Claude Code Plugin

Slash commands included in `.claude/commands/`:

| Command | Action |
|---------|--------|
| `/gemini <prompt>` | Quick ask_gemini call |
| `/gemini-research <topic>` | Start deep research |
| `/gemini-review <file>` | Code review |
| `/gemini-models` | List available models |
| `/ask-model [model] <prompt>` | Ask any model (GPT-4o, Llama, Gemini, etc.) |

Subagents in `.claude/agents/` (auto-invoked by Claude Code):

| Agent | Trigger | Capability |
|-------|---------|------------|
| `gemini-researcher` | "research X", "find out about Y" | Deep Research Agent, 40+ sources |
| `gemini-analyzer` | "analyze codebase", "security audit" | 1M token context window |
| `model-orchestrator` | "ask GPT-4o", "compare models", "use Llama" | Routes to 400+ models |

---

## Multi-Model Architecture

omni-ai-mcp uses **Claude as the orchestrator** with other models as tools. This is different from provider replacement:

```
User → Claude Code
           ↓ (orchestrates)
      omni-ai-mcp tools
      ├── ask_model("openai/gpt-4o")   → OpenRouter → GPT-4o
      ├── ask_model("meta-llama/...")  → OpenRouter → Llama 3
      ├── ask_gemini(...)              → Gemini API → Gemini Pro
      └── gemini_deep_research(...)    → Gemini API → Deep Research
```

### Natural multi-model conversations

With the `model-orchestrator` subagent, Claude Code automatically routes to the right model:

```
"Ask GPT-4o to review this code"
→ model-orchestrator calls ask_model(model="openai/gpt-4o", ...)

"Compare how Gemini and Llama respond to this prompt"
→ model-orchestrator calls ask_model twice, presents comparison

"What's the best model for translating legal documents?"
→ model-orchestrator recommends and demonstrates
```

### Alternative: Claude Code Router

For users who want to **replace** Claude's backend entirely (e.g., use Gemini as the primary model for all Claude Code interactions), [claude-code-router](https://github.com/musistudio/claude-code-router) is a complementary tool:

```json
// ~/.claude-code-router/config.json
{
  "Providers": [{"name": "openrouter", "api_key": "sk-or-..."}],
  "Router": {
    "default": "openrouter,openai/gpt-4o",
    "think": "openrouter,anthropic/claude-3.5-sonnet"
  }
}
```

> **omni-ai-mcp** = Claude orchestrates other models as tools
> **claude-code-router** = Replace Claude's backend with another model entirely

---

## Security

- Path sandboxing: all file access restricted to `GEMINI_SANDBOX_ROOT`
- Secrets sanitization: API keys masked in logs
- XML sanitization: LLM output sanitized before parsing
- Atomic file writes with automatic backups
- Rate limiting via provider-side quotas

---

## Development

```bash
# Run tests
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v  # requires GEMINI_API_KEY

# Quick import check
python -c "from app.core.config import config; print(f'v{config.version}')"

# Reinstall after changes
cp -r app/ ~/.claude-mcp-servers/omni-ai-mcp/
cp run.py ~/.claude-mcp-servers/omni-ai-mcp/
# Restart Claude Code
```

---

## License

MIT — see [LICENSE](LICENSE)
