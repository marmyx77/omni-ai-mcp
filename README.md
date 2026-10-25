# omni-ai-mcp

**The complete AI bridge for Claude Code** — Gemini's exclusive capabilities (video, TTS, 1M context, RAG, Deep Research) plus 400+ models via OpenRouter. One MCP server, every AI model, zero friction.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Version 4.8.0](https://img.shields.io/badge/version-4.8.0-green.svg)](https://github.com/marmyx77/omni-ai-mcp/releases)
[![PyPI](https://img.shields.io/badge/PyPI-omni--ai--mcp-blue.svg)](https://pypi.org/project/omni-ai-mcp/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

---

## Why This Exists

Claude is exceptional at reasoning and code generation. But sometimes you need more:

- A **second opinion** from a different AI model (GPT-4o, Llama, Mistral, Claude via OpenRouter)
- **Real-time web search** with Google grounding and source citations
- **Autonomous deep research** that runs for minutes and produces structured reports from 40+ sources
- **Video generation and editing** with Gemini Omni Flash: text/image to video, interpolation, conversational edits and extensions, native audio, up to 4K
- **Image generation** with the Nano Banana family (Pro, 2.1, 2 Lite): accurate infographics, panoramic formats, up to 4K
- **Music generation** with Lyria: full songs with vocals and lyrics, or 30-second clips
- **Text-to-speech** with Gemini 3.8 TTS: hundreds of library voices, custom designed and replicated voices, two-speaker dialogue
- **Speech to text and video understanding**: diarized transcripts, YouTube and long-video analysis
- **Multimodal embeddings** and a **managed coding agent** (Antigravity) running in Google's sandbox
- **RAG** for querying your own documents with citations
- **Large codebase analysis** with Gemini's 1M token context window
- **Multi-turn conversations** with cloud persistence (55-day retention, resume from any device)
- Access to **400+ models** through one unified interface

omni-ai-mcp bridges Claude Code with Google Gemini and OpenRouter, enabling Claude to orchestrate any AI model as a tool.

---

## What's New in v4.8.0

Everything Google shipped in the Gemini API between June and October 2026, except the real-time Live API models (WebSocket streaming does not fit an MCP request/response tool). Verified live on 2026-10-25.

- **`pro` is now Gemini 4 Argon**, Google's new flagship (1M context, thinking low/medium/high). The registry recognises Gemini 4 codenames, so its successors are picked up automatically.
- **Video moved to Gemini Omni Flash.** Veo 3.1 Preview was shut down in the Gemini API on 2026-10-22. `gemini_generate_video` now does text/image to video, first+last frame interpolation, subject references, conversational edits and extensions of a generated clip, 360p to 4K, 3-10 s with native audio.
- **Nano Banana 2.1** for fast images: panoramic 1:4, 4:1, 1:8, 8:1, 1K to 4K, up to 14 reference images, Google Search grounding, thinking levels; new `lite` model.
- **Gemini 3.8 TTS** (Flash and Flash-Lite): any of hundreds of Voice Library voices, per-turn style direction, plus voice design and voice replication.
- **New tools**: `gemini_analyze_video` (files or YouTube, static or agentic processing), `gemini_generate_music` (Lyria 3.5 and Lyria Clip), `gemini_list_voices`, `gemini_design_voice`, `gemini_replicate_voice`, `gemini_embed` (Gemini Embedding 2, multimodal), `gemini_agent_task` (Antigravity managed agent).
- **Also**: Deep Research Max (`depth="max"`), Robotics ER spatial reasoning (`model="robotics"` in image/video analysis), Gemma 4 through `ask_model`, Flash-Lite in image analysis.
- **API hygiene**: `temperature`/`top_p`/`top_k` are no longer sent to Gemini 3.6+ (deprecated upstream, 400 announced for future models); the output budget is 64K by default (`GEMINI_MAX_OUTPUT_TOKENS`) because thinking and answer share it; the Pro→Flash quota fallback now covers Argon and skips spending-cap errors.

## What's New in v4.7.0

**`gemini_transcribe_audio`.** Speech to text with Gemini's dedicated transcription model (`gemini-3.5-transcribe` today, newest auto-detected): 85+ languages detected automatically with code-switching, optional speaker diarization, word-level timestamps rendered as timestamped sentences, custom vocabulary, `smart` (fillers removed, numbers and dates formatted) or `verbatim` mode (`auto` picks verbatim when timestamps are on, as the API requires). Files up to 1 hour; large files go through the Files API transparently. Save the transcript as text or structured JSON with `output_path`. Requires `google-genai >= 2.20.0`.

## What's New in v4.6.0

**Model auto-detection.** The server no longer ships a hardcoded "latest" model ID. At runtime it lists the models your Gemini API key exposes and, per category (pro, flash, flash-lite, image, video, TTS, deep research), picks the newest one by version number — stable preferred over preview at the same version. When Google ships `gemini-4.0-flash`, `flash` resolves to it on the next cache refresh (1 hour), with no release of this package.

- `gemini_list_models` now shows **where each choice came from** (auto-detected, env override, static fallback) and the runners-up.
- An explicit `GEMINI_MODEL_*` variable always wins; `GEMINI_MODEL_AUTODETECT=false` restores the static lists.
- New `flash-lite` alias for `ask_gemini` / `ask_model`; `veo31_lite` for video. Veo 3.0 / 2.0 removed (gone upstream).

## Multi-Provider: Gemini + OpenRouter

### Quick start

```python
# Ask any of 400+ models — auto-routes from model name
ask_model("Explain quantum computing", model="openai/gpt-4o")
ask_model("Write a poem", model="meta-llama/llama-3.3-70b-instruct")
ask_model("Review this code", model="gemini-3.1-pro-preview")  # auto-routes to Gemini native API

# If no Gemini key but OpenRouter key exists, Gemini models route via OpenRouter automatically
ask_model("Summarize this", model="flash")  # newest Flash, or google/ prefix on OpenRouter without a Gemini key

# Discover all available models
gemini_list_models()
```

### Dynamic Model Registry

The server lists the models your key exposes at runtime and resolves every alias to the **newest matching model by version** (v4.6.0). If a model disappears upstream, the next one down takes over. `gemini_list_models` shows the resolved ID per category and its provenance.

```bash
# Override via env vars if needed:
export GEMINI_MODEL_PRO=gemini-3.1-pro-preview
export OPENROUTER_DEFAULT_MODEL=openai/gpt-4o
```

### Smart Routing Rules

1. Explicit Gemini model + `GEMINI_API_KEY` -> **always** Gemini native API (fastest, cheapest)
2. Gemini model + no Gemini key + `OPENROUTER_API_KEY` -> OpenRouter `google/` prefix (automatic fallback)
3. `lyria-*`, `deep-research-*` and other media/agent models -> Gemini native only (no OpenRouter equivalent); `gemma-*` -> Gemini native, mirrored on OpenRouter
4. OpenRouter model (`openai/`, `meta-llama/`, etc.) -> OpenRouter (requires `OPENROUTER_API_KEY`)

### PyPI Distribution

```bash
pip install omni-ai-mcp
omni-ai-mcp-setup  # interactive setup wizard
```

### Claude Desktop Extension (.dxt)

Install with one click — no Python setup required:

1. Download `omni-ai-mcp-vX.Y.Z.dxt` from [GitHub Releases](https://github.com/marmyx77/omni-ai-mcp/releases)
2. Double-click the file (macOS/Windows) or drag it into Claude Desktop
3. Enter your Gemini API key when prompted (OpenRouter key is optional)
4. Done — all 28 tools are immediately available in Claude Desktop

The `.dxt` bundle includes all Python dependencies — users don't need to install anything else.

---

## 28 Tools

### Multi-Provider
| Tool | Description |
|------|-------------|
| `ask_model` | Ask any AI: Gemini or 400+ models via OpenRouter — auto-routes from model name |
| `gemini_list_models` | Live model discovery: Gemini registry + OpenRouter catalog, deprecation warnings |

### Text & Reasoning
| Tool | Description | Model |
|------|-------------|-------|
| `ask_gemini` | Text generation with thinking mode, multi-turn, dual storage (local/cloud) | newest flagship (Gemini 4 Argon) |
| `gemini_code_review` | Security, performance, and quality analysis | newest flagship |
| `gemini_brainstorm` | Creative ideation with 6 methodologies (SCAMPER, TRIZ, etc.) | newest flagship |
| `gemini_challenge` | Devil's advocate — find flaws in ideas, plans, and code | newest flagship |
| `gemini_embed` | Multimodal embeddings (text, images, audio, video, PDF) for search and clustering | Gemini Embedding 2 |

### Code
| Tool | Description | Model |
|------|-------------|-------|
| `gemini_analyze_codebase` | Whole-codebase analysis up to 1M tokens / 5MB | newest flagship |
| `gemini_generate_code` | Structured code generation with dry-run preview and XML output | newest flagship |
| `gemini_agent_task` | Delegate a multi-step task to the Antigravity agent in Google's Linux sandbox (code, files, web) | Antigravity Agent |

### Research & Web
| Tool | Description | Model |
|------|-------------|-------|
| `gemini_web_search` | Real-time search with Google grounding & citations | newest Gemini Flash |
| `gemini_deep_research` | Autonomous 5-60 min research, 40+ sources, structured report (`depth="max"` for Deep Research Max) | Deep Research Agent |

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
| `gemini_analyze_image` | Vision: describe, OCR, Q&A; spatial reasoning (points, boxes) with `model="robotics"` | newest Gemini Flash |
| `gemini_analyze_video` | Video understanding from a file or YouTube; agentic processing for long videos | newest Gemini Flash |
| `gemini_generate_image` | Nano Banana Pro / 2.1 / 2 Lite: infographics, readable text, panoramic formats, up to 4K, 14 references | newest Nano Banana |
| `gemini_generate_video` | Omni Flash: generate, edit, extend, interpolate; 3-10 s with native audio, up to 4K | newest Gemini Omni Flash |
| `gemini_generate_music` | Lyria: full songs with vocals and lyrics, or 30 s clips (MP3) | newest Lyria |
| `gemini_text_to_speech` | Gemini 3.8 TTS: any library/designed/replicated voice, style direction, two-speaker dialogue | newest Gemini Flash TTS |
| `gemini_list_voices` | Browse the Voice Library (hundreds of voices) with filters | - |
| `gemini_design_voice` | Create a custom voice from a description | newest Gemini Flash TTS |
| `gemini_replicate_voice` | Replicate a consenting speaker's voice (reference + consent audio) | newest Gemini Flash TTS |
| `gemini_transcribe_audio` | Speech to text: 85+ languages, speaker diarization, word timestamps, custom vocabulary, up to 1 h | newest Gemini Transcribe |

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

### Install a release tag on another machine

For a machine that only runs the server (a home server, a second workstation), install a **GitHub release tag** with the versioned script — no checkout, nothing copied by hand. Updating = rerun with the newer tag:

```bash
curl -fsSL https://raw.githubusercontent.com/marmyx77/omni-ai-mcp/main/scripts/install_release.sh | bash            # latest tag
curl -fsSL https://raw.githubusercontent.com/marmyx77/omni-ai-mcp/main/scripts/install_release.sh | bash -s v4.6.5  # pin a tag
```

It creates `~/.claude-mcp-servers/omni-ai-mcp/venv`, installs `omni-ai-mcp @ git+https://github.com/marmyx77/omni-ai-mcp@<tag>`, and points `mcpServers.omni-ai-mcp` in `~/.claude.json` at it (API keys already there are kept; otherwise export `GEMINI_API_KEY` before running). `--status` prints installed vs latest tag.

### Manual Install

```bash
pip install 'mcp[cli]>=1.0.0,<2' 'google-genai>=2.33.0' pydantic defusedxml filelock

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

### Video Generation and Editing

```
"Generate a video of ocean waves at sunset, seagulls flying, sound of waves and wind"
```

- Model: Gemini Omni Flash (Veo 3.1 Preview was shut down in the Gemini API on 2026-10-22)
- Duration: 3-10 seconds (`duration`), aspect 16:9 or 9:16, resolution 360p/720p native, 1080p/4K upscaled
- Native audio: describe dialogue, effects and music in the prompt; timecodes work (`[0-3s] ... [3-6s] ...`)
- Images: a starting frame, first+last frames (`<FIRST_FRAME> <LAST_FRAME>`) or references (`<IMAGE_REF_0>`)
- Edit or extend the result conversationally: pass the returned `continuation_id` with a short instruction ("Make it night. Keep everything else the same.")
- Editing or extending an uploaded clip (≤ 10 s) is not available in the EEA, Switzerland and the UK; edits of generated clips are

### Music Generation

```python
gemini_generate_music(prompt="Upbeat Italian pop song about summer in Turin, female vocals, about 2 minutes, verse-chorus-verse-chorus-bridge-chorus")
gemini_generate_music(prompt="Calm lo-fi piano loop, instrumental", model="clip")   # 30 s
```

Returns an MP3 (44.1 kHz stereo) and the generated lyrics.

### Video Understanding

```python
gemini_analyze_video(prompt="List the key moments with MM:SS timestamps", youtube_url="https://www.youtube.com/watch?v=...")
gemini_analyze_video(prompt="When does the speaker mention pricing?", video_path="talk.mp4", processing="agentic")
```

### Image Generation

```
"Generate an image of a futuristic Tokyo street at night, neon lights reflecting on wet pavement,
cinematic, shot on 35mm lens"
```

- Models: `pro` (Nano Banana Pro, default), `flash` (Nano Banana 2.1), `lite` (Nano Banana 2 Lite)
- Resolution: 512, 1K, 2K or 4K (`auto`: 2K on pro, model default elsewhere)
- Aspect ratios: 1:1, 16:9, 9:16, 3:2, 4:5 and more; panoramic 1:4, 4:1, 1:8, 8:1 on `flash`
- Up to 14 `input_images` to edit, fuse or keep characters consistent; `google_search=true` grounds facts
- Use descriptive sentences, not keyword lists

### Text-to-Speech

```
"Convert this article to speech using the Charon voice (informative, neutral)"
```

30 featured studio voices (Zephyr, Puck, Charon, Kore, Sulafat...) plus hundreds more in the Voice Library: browse them with `gemini_list_voices(language_codes=["it-IT"])`. Direct the delivery with `style="slow, warm audiobook narration"`. Create your own with `gemini_design_voice` (from a description) or `gemini_replicate_voice` (from a consenting speaker's recording).

Multi-speaker dialogue:

```python
gemini_text_to_speech(
    text="Host: Welcome!\nGuest: Thanks for having me!",
    speakers=[
        {"name": "Host", "voice": "Charon", "style": "warm and welcoming"},
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

Levels: `auto` (default, the model decides), `low`, `medium`, `high`. Gemini 3+ models always reason: `auto` is not zero.

---

## Model Selection

### Text Models

| Alias | Category | Best For |
|-------|----------|----------|
| `pro` | newest flagship (Gemini 4 Argon today) | Complex reasoning, coding, math, agents |
| `flash` / `fast` | newest Gemini Flash | Balanced speed/quality |
| `flash-lite` | newest Gemini Flash-Lite | High-volume, simple tasks |

Aliases resolve at runtime to the newest model of that category your API key exposes (stable preferred over preview at the same version; newer naming schemes such as Gemini 4 codenames and Nano Banana win over older ones). If Google stops listing a family while still serving it, the registry verifies the known IDs by name. Run `gemini_list_models` to see the concrete IDs and where each one came from; set `GEMINI_MODEL_*` to pin one.

### OpenRouter Models (via `ask_model`)

| Provider | Example Model ID | Notes |
|----------|-----------------|-------|
| OpenAI | `openai/gpt-4o` | GPT-4o, o3, o4-mini |
| Meta | `meta-llama/llama-3.3-70b-instruct` | Open source, fast |
| Anthropic | `anthropic/claude-3.5-sonnet` | Claude via OpenRouter |
| Mistral | `mistralai/mistral-large-2512` | Strong on EU languages |
| Google | `google/gemini-4-argon` | Gemini and Gemma via OpenRouter (fallback) |
| 340+ more | — | `gemini_list_models()` to browse |

---

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | **required** | Google Gemini API key |
| `OPENROUTER_API_KEY` | — | OpenRouter key (enables `ask_model` for 400+ models) |
| `GEMINI_MODEL_AUTODETECT` | `true` | Pick the newest model per category from the live API list; `false` = static fallbacks only |
| `GEMINI_MODEL_PRO` / `_FLASH` / `_FLASH_LITE` | auto-detected | Pin a text model (an explicit value always wins over auto-detect) |
| `GEMINI_MODEL_IMAGE_PRO` / `_IMAGE_FLASH` / `_IMAGE_LITE` | auto-detected | Pin an image model |
| `GEMINI_MODEL_VIDEO` | auto-detected | Pin the video model (Gemini Omni Flash) |
| `GEMINI_MODEL_TTS_FLASH` / `_TTS_LITE` | auto-detected | Pin a TTS model |
| `GEMINI_MODEL_TRANSCRIBE` | auto-detected | Pin the speech-to-text model |
| `GEMINI_MODEL_MUSIC` / `_MUSIC_CLIP` | auto-detected | Pin a Lyria model |
| `GEMINI_MODEL_DEEP_RESEARCH` / `_DEEP_RESEARCH_MAX` | auto-detected | Pin a research agent |
| `GEMINI_MODEL_AGENT` | auto-detected | Pin the Antigravity agent version |
| `GEMINI_MODEL_EMBEDDING` | auto-detected | Pin the embedding model |
| `GEMINI_MODEL_ROBOTICS` | auto-detected | Pin the Robotics ER model |
| `GEMINI_MAX_OUTPUT_TOKENS` | `65536` | Output budget per request (thinking + answer share it on Gemini 3+) |
| `OPENROUTER_DEFAULT_MODEL` | `openai/gpt-4o` | Default OpenRouter model |
| `OPENROUTER_TIMEOUT` | `120` | OpenRouter generation timeout in seconds (raise for search models like `perplexity/sonar-deep-research`) |
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

Included in `.claude/commands/` (auto-available in Claude Code when working inside this repo, or copy to `~/.claude/commands/` for global access):

| Command | Action |
|---------|--------|
| `/gemini <prompt>` | Ask Gemini Pro anything |
| `/gemini-research <topic>` | Autonomous deep research (40+ sources, 5-30 min) |
| `/gemini-review <file>` | Code review focused on bugs, security, performance |
| `/gemini-challenge <idea>` | Devil's Advocate — find flaws in a plan or architecture |
| `/gemini-analyze <path>` | Codebase analysis with 1M token context window |
| `/gemini-brainstorm <topic>` | Structured brainstorming (6 methodologies) |
| `/gemini-models` | List available models (Gemini + OpenRouter) |
| `/ask-model [model] <prompt>` | Ask any model: GPT-4o, Llama, Mistral, Gemini, etc. |
| `/cowork <task>` | Claude + Gemini working in parallel on the same task |

### Subagents

Included in `.claude/agents/` — Claude Code activates these automatically based on context:

| Agent | Trigger | Capability |
|-------|---------|------------|
| `gemini-researcher` | "research X", "investigate Y", "find sources on Z" | Deep Research Agent, 40+ sources |
| `gemini-analyzer` | "analyze codebase", "security audit", "review architecture" | 1M token context window |
| `model-orchestrator` | "ask GPT-4o", "compare models", "use Llama for this" | Routes to 400+ models via OpenRouter |
| `cowork` | "second opinion", "verify with Gemini", "stress test this" | Claude + Gemini parallel analysis with synthesis |

### Install globally (all projects)

```bash
cp -r .claude/commands/* ~/.claude/commands/
cp -r .claude/agents/* ~/.claude/agents/
```

---

## Multi-Model Architecture

omni-ai-mcp uses **Claude as the orchestrator** with other models as tools:

```
User -> Claude Code
            (orchestrates)
       omni-ai-mcp tools
       +-- ask_model("openai/gpt-4o")       -> OpenRouter -> GPT-4o
       +-- ask_model("meta-llama/...")       -> OpenRouter -> Llama 3
       +-- ask_model("gemini-4-argon")       -> Gemini API (native)
       +-- ask_gemini(...)                   -> Gemini API -> newest flagship
       +-- gemini_deep_research(...)         -> Interactions API -> Deep Research Agent
       +-- gemini_agent_task(...)            -> Interactions API -> Antigravity Agent (Google sandbox)
       +-- gemini_generate_video(...)        -> Interactions API -> Gemini Omni Flash
```

This is different from **provider replacement** tools like [claude-code-router](https://github.com/musistudio/claude-code-router) which replace Claude's backend entirely. omni-ai-mcp keeps Claude in control while giving it access to every AI model as a tool.

---

## Architecture

```
omni-ai-mcp/
+-- app/
|   +-- server.py              # FastMCP -- 28 @mcp.tool() registrations
|   +-- core/                  # Config, structured logging, security
|   +-- services/
|   |   +-- gemini.py          # Gemini client + generate_with_fallback()
|   |   +-- model_registry.py  # Dynamic model discovery (API + cache, multi-scheme, probing)
|   |   +-- interactions.py    # Interactions API helpers (files, polling, outputs, media)
|   |   +-- openrouter.py      # OpenRouter client (OpenAI-compatible)
|   |   +-- persistence.py     # SQLite conversation storage + index
|   +-- tools/                 # Tool implementations by domain
|   |   +-- text/              # ask_gemini, ask_model, models, embed, brainstorm, etc.
|   |   +-- code/              # analyze_codebase, generate_code
|   |   +-- media/             # image, video (Omni), music (Lyria), TTS + voices, transcription, video analysis
|   |   +-- web/               # web_search, deep_research, agent_task (Antigravity)
|   |   +-- rag/               # file_store, file_search, upload
|   +-- schemas/               # Pydantic v2 validation
|   +-- utils/                 # @file expansion, token estimation
+-- tests/                     # Test suite (unit + integration; counts: see CLAUDE.md)
+-- .claude/
|   +-- commands/              # Slash commands
|   +-- agents/                # Subagents
+-- setup.sh                   # One-command install
+-- manifest.json              # DXT extension manifest (Claude Desktop)
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

### v4.8.0
- `pro` → Gemini 4 Argon; video on Gemini Omni Flash (Veo 3.1 Preview shut down upstream); Nano Banana 2.1 and Lite; Gemini 3.8 TTS with Voice Library, voice design and replication
- New tools: video understanding, music (Lyria), voices ×3, multimodal embeddings, Antigravity agent; Deep Research Max; Robotics ER; Gemma 4
- No sampling parameters to Gemini 3.6+, 64K output budget, quota fallback covers Argon; registry verifies unlisted models by name

### v4.7.0
- `gemini_transcribe_audio`: speech to text (85+ languages, diarization, word timestamps, vocabulary, smart/verbatim); `google-genai>=2.20.0`

### v4.6.5
- Deep Research: `continuation_id` with an empty query retrieves/resumes a previous research (timed-out reports were unreachable before); with a query it chains a follow-up

### v4.6.4
- Deep Research: agent resolved per call from the registry; errors name the API message, agent and package version; editable install recommended so sessions never run stale code

### v4.6.3
- `ask_gemini` thinking: `auto` (default, replaces the misleading `off`) and `medium`; Gemini 3+ always reasons, so `auto` is not zero

### v4.6.2
- Pin `mcp[cli]<2`: mcp 2.x (2026-09-07) renamed `FastMCP` → `MCPServer`, so a fresh install crashed at import

### v4.6.1
- Clean sdist (a stray working note had slipped into the 4.6.0 sdist); `ask_gemini` picks the thinking knob on the resolved model, `flash-lite` alias

### v4.6.0
- Model auto-detection: every alias resolves to the newest matching model the API exposes; `gemini_list_models` reports provenance
- `flash-lite` and `veo31_lite` aliases; Veo 3.0 / 2.0 removed (gone upstream)
- Removed 34 dead integration tests that CI had been ignoring via `continue-on-error`; integration job is now blocking

### v4.4.0
- Updated all model defaults to the latest Gemini IDs (verified live): flash → `gemini-3.5-flash`, flash-lite → `gemini-3.1-flash-lite`, image → `gemini-3-pro-image` / `gemini-3.1-flash-image`, TTS → `gemini-3.1-flash-tts-preview`
- Fixed deep research: `deep-research-pro-preview` returned `404 NOT_FOUND` → now `deep-research-preview-04-2026`
- Registry fallbacks refreshed (`imagen-3.0` → `imagen-4.0`, added `veo-3.1-lite`)

### v4.2.0
- `/gemini-illustrate` and `/gemini-image` commands; richer `gemini_generate_image` tool description

### v4.1.0
- `gemini_generate_image` image editing (`input_images`); `gemini_analyze_image` multi-image + `media_resolution`

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
