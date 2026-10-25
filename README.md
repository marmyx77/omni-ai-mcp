# omni-ai-mcp

**Google Gemini's full toolbox, plus 400+ models via OpenRouter, as one MCP server for Claude.**
Video, music, voice, images, deep research, a managed coding agent, 1M-token analysis and more: Claude stays the orchestrator and calls them as tools.

[![Tests](https://github.com/marmyx77/omni-ai-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/marmyx77/omni-ai-mcp/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/omni-ai-mcp.svg)](https://pypi.org/project/omni-ai-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/omni-ai-mcp.svg)](https://pypi.org/project/omni-ai-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

```
You → Claude Code / Claude Desktop
        └─ omni-ai-mcp (28 tools)
             ├─ Gemini API ── Gemini 4 Argon · 3.8 Flash · Nano Banana · Omni Flash · Lyria · 3.8 TTS · Transcribe
             │                Deep Research · Antigravity agent · Embedding 2 · Robotics ER · File Search
             └─ OpenRouter ── GPT, Claude, Llama, Mistral, Grok, DeepSeek, Qwen, Perplexity… (400+)
```

---

## Contents

[Why](#why) · [What's new](#whats-new-in-48) · [Install](#install) · [Tools](#the-28-tools) · [Examples](#examples) · [Models](#models) · [Configuration](#configuration) · [Claude Code plugin](#claude-code-plugin) · [Docker](#docker) · [Troubleshooting](#troubleshooting) · [Costs](#costs) · [Development](#development) · [Security](#security)

---

## Why

Claude is excellent at reasoning and code. Some jobs need what only Google ships, or a second opinion from another model family:

- **Generate and edit media**: video with native audio (Gemini Omni Flash), images up to 4K with readable text (Nano Banana), full songs with vocals (Lyria), studio-grade speech in hundreds of voices (Gemini 3.8 TTS)
- **Understand media**: diarized transcripts, YouTube and long-video analysis, image OCR, spatial reasoning
- **Research**: Google-grounded search with citations, autonomous Deep Research reports from dozens of sources
- **Delegate work**: the Antigravity agent runs code, edits files and browses the web in its own Google-hosted sandbox
- **Scale context**: analyse a whole codebase in Gemini's 1M-token window
- **Retrieve**: RAG over your documents, multimodal embeddings for semantic search
- **Compare**: ask any of 400+ models through one tool

Models are **auto-detected** from the live API: when Google ships a newer Flash, Pro, image, TTS or video model, the server uses it on the next refresh, with no release of this package.

## What's new in 4.8

Everything Google shipped in the Gemini API from June to October 2026, except the real-time Live API models. Verified live with one real call per tool.

- **Gemini 4 Argon** is the new `pro`. **Gemini Omni Flash** replaces Veo for video (Veo 3.1 Preview was shut down in the Gemini API on 2026-10-22).
- **Nano Banana 2.1 and 2 Lite** for images, **Gemini 3.8 TTS** with the Voice Library, voice design and voice replication.
- **Seven new tools**: video understanding, music, three voice tools, multimodal embeddings, the Antigravity agent. Plus Deep Research Max, Robotics ER and Gemma 4.
- **4.8.2 is a security release**: every file a tool reads or writes now stays inside the workspace, credentials are always refused, and OpenRouter calls retry on transient errors. See [Security](#security).

Full history: [CHANGELOG.md](https://github.com/marmyx77/omni-ai-mcp/blob/main/CHANGELOG.md).

---

## Install

You need a **Gemini API key** ([get one](https://aistudio.google.com/apikey)) and, optionally, an **OpenRouter key** ([openrouter.ai](https://openrouter.ai)) for non-Google models.

### Claude Code: one command (recommended)

With [uv](https://docs.astral.sh/uv/) installed, nothing else is needed: `uvx` fetches the package from PyPI with a suitable Python.

```bash
claude mcp add omni-ai-mcp --scope user \
  -e GEMINI_API_KEY=YOUR_GEMINI_KEY \
  -e OPENROUTER_API_KEY=YOUR_OPENROUTER_KEY \
  -- uvx omni-ai-mcp
```

Drop the `OPENROUTER_API_KEY` line if you only use Gemini. Restart Claude Code and check with `claude mcp list`. To pick up a new release, run `uv cache clean omni-ai-mcp` (or register `uvx omni-ai-mcp@latest`, which checks PyPI at every start).

### Claude Desktop: one-click extension

1. Download `omni-ai-mcp-vX.Y.Z.dxt` from [Releases](https://github.com/marmyx77/omni-ai-mcp/releases/latest)
2. Double-click it (or drag it into Claude Desktop)
3. Paste your Gemini key (OpenRouter is optional)

### Claude Code plugin

The plugin bundles the MCP server with the [slash commands and subagents](#claude-code-plugin). Download `omni-ai-mcp-plugin-vX.Y.Z.zip` from [Releases](https://github.com/marmyx77/omni-ai-mcp/releases/latest) and install it from Claude Code, or run `/setup` inside a clone of this repository.

### pip

```bash
pip install omni-ai-mcp      # Python 3.10+
omni-ai-mcp-setup            # interactive wizard: writes the server into ~/.claude.json
```

### From source (contributors)

```bash
git clone https://github.com/marmyx77/omni-ai-mcp.git && cd omni-ai-mcp
./setup.sh YOUR_GEMINI_KEY [YOUR_OPENROUTER_KEY]
```

`setup.sh` creates a virtualenv in `~/.claude-mcp-servers/omni-ai-mcp`, installs the checkout in **editable** mode (a `git pull` is the whole update) and registers the server in Claude Code.

### Another machine, pinned to a release

For a home server or second workstation that should run a specific GitHub release:

```bash
curl -fsSL https://raw.githubusercontent.com/marmyx77/omni-ai-mcp/main/scripts/install_release.sh | bash             # latest tag
curl -fsSL https://raw.githubusercontent.com/marmyx77/omni-ai-mcp/main/scripts/install_release.sh | bash -s vX.Y.Z   # a specific tag
```

It picks a Python ≥ 3.10 (installing one with uv if needed), installs the tag into `~/.claude-mcp-servers/omni-ai-mcp/venv` and points `~/.claude.json` at it, keeping any API keys already configured (or reading `GEMINI_API_KEY` / `OPENROUTER_API_KEY` from the environment). `--status` compares the installed version with the latest tag.

---

## The 28 tools

**Text and reasoning**

| Tool | What it does | Model |
|------|--------------|-------|
| `ask_gemini` | Ask Gemini: thinking levels, multi-turn memory (local SQLite or 55-day cloud), `@file` references | newest flagship (Gemini 4 Argon) |
| `ask_model` | Ask any model: Gemini, Gemma, or 400+ via OpenRouter; routes from the model name | any |
| `gemini_code_review` | Security, performance and quality review | newest flagship |
| `gemini_brainstorm` | Ideation with 6 methodologies (SCAMPER, Design Thinking, …) | newest flagship |
| `gemini_challenge` | Devil's advocate: finds the flaws in a plan, idea or code | newest flagship |
| `gemini_embed` | Multimodal embeddings (text, image, audio, video, PDF) for search and clustering | Gemini Embedding 2 |
| `gemini_list_models` | Which model each alias resolves to, and why; OpenRouter catalogue | — |
| `gemini_list_conversations` · `gemini_delete_conversation` | Manage conversation memory | — |

**Code and agents**

| Tool | What it does | Model |
|------|--------------|-------|
| `gemini_analyze_codebase` | Whole-codebase analysis in a 1M-token window (5 MB cap) | newest flagship |
| `gemini_generate_code` | Structured code generation with dry-run preview | newest flagship |
| `gemini_agent_task` | Delegate a multi-step task to Google's Antigravity agent: Bash/Python/Node, files and web in a hosted Linux sandbox | Antigravity |

**Research**

| Tool | What it does | Model |
|------|--------------|-------|
| `gemini_web_search` | Answers grounded in Google Search, with citations | newest Flash |
| `gemini_deep_research` | Autonomous multi-source research report (minutes); `depth="max"` for Deep Research Max; resumable | Deep Research agent |
| `gemini_file_search` · `gemini_create_file_store` · `gemini_upload_file` · `gemini_list_file_stores` | RAG over your documents with citations | newest Flash |

**Media**

| Tool | What it does | Model |
|------|--------------|-------|
| `gemini_generate_image` | Images and edits: infographics with accurate data, readable text, panoramic formats, up to 4K, 14 reference images | Nano Banana Pro / 2.1 / 2 Lite |
| `gemini_generate_video` | Video with native audio: from text or images, interpolation, conversational edits and extensions; 3-10 s, up to 4K | Gemini Omni Flash |
| `gemini_generate_music` | Full songs with vocals and lyrics, or 30-second clips (MP3) | Lyria 3.5 / Lyria Clip |
| `gemini_text_to_speech` | Speech in any library, designed or replicated voice; style direction; two-speaker dialogue | Gemini 3.8 Flash TTS |
| `gemini_list_voices` · `gemini_design_voice` · `gemini_replicate_voice` | Browse hundreds of voices, create one from a description, or replicate a consenting speaker | Gemini 3.8 Flash TTS |
| `gemini_transcribe_audio` | Speech to text: 85+ languages, speakers, word timestamps, custom vocabulary, up to 1 h | Gemini 3.5 Transcribe |
| `gemini_analyze_image` | Describe, OCR, compare; spatial reasoning (points, boxes) with `model="robotics"` | newest Flash / Robotics ER |
| `gemini_analyze_video` | Understand a video file or YouTube link; agentic processing for long videos | newest Flash |

---

## Examples

In Claude Code you ask in plain language and Claude picks the tool. The calls below show what it sends.

**Second opinion from another model family**
```python
ask_model(prompt="Review this auth flow for security issues: …", model="openai/gpt-4o")
ask_model(prompt="Same question", model="pro")                    # newest Gemini flagship
ask_model(prompt="Fact-check with sources", model="perplexity/sonar-pro")
```

**Deep research that survives timeouts**
```python
gemini_deep_research(query="Compare open-source vector databases for 100M embeddings", depth="max")
gemini_deep_research(query="", continuation_id="v1_…")           # timed out? fetch the finished report
```

**Video: generate, then edit conversationally**
```python
gemini_generate_video(prompt="A paper boat on a calm pond at dawn, gentle water sounds", resolution="1080p", duration=6)
gemini_generate_video(prompt="Make it night. Keep everything else the same.", continuation_id="v1_…")
gemini_generate_video(prompt="<FIRST_FRAME> <LAST_FRAME> slow dolly between the two shots", image_paths=["a.png", "b.png"])
```
Editing or extending an **uploaded** clip (≤ 10 s) is not available in the EEA, Switzerland and the UK; edits of generated clips are.

**Images**
```python
gemini_generate_image(prompt="Infographic: how a heat pump works, labelled, flat style", model="pro", image_size="4K")
gemini_generate_image(prompt="Panorama of the Alps at sunset", model="flash", aspect_ratio="8:1", google_search=True)
```

**Music and voice**
```python
gemini_generate_music(prompt="Upbeat Italian pop song about summer in Turin, female vocals, about 2 minutes")
gemini_list_voices(language_codes=["it-IT"], contexts=["Audiobook"])
gemini_text_to_speech(text="Benvenuti al podcast.", voice="Kore", style="warm, slow narration", language="it-IT")
gemini_text_to_speech(text="Host: Welcome!\nGuest: Thanks for having me!",
                      speakers=[{"name": "Host", "voice": "Charon", "style": "welcoming"}, {"name": "Guest", "voice": "Aoede"}])
gemini_design_voice(description="A calm Italian radio host in her 40s, warm and precise", language_code="it-IT")
```

**Transcription and video understanding**
```python
gemini_transcribe_audio(audio_path="meeting.m4a", diarization=True, word_timestamps=True)
gemini_analyze_video(prompt="Key moments with MM:SS timestamps", youtube_url="https://www.youtube.com/watch?v=…")
gemini_analyze_video(prompt="When is pricing discussed?", video_path="webinar.mp4", processing="agentic")
```

**Delegate to the Antigravity agent**
```python
gemini_agent_task(task="Download the last 12 months of ECB rates, chart them and save the chart as PNG", output_dir="./out")
```

**Codebase, files and memory**
```python
gemini_analyze_codebase(prompt="Find architecture issues", files=["app/**/*.py"], analysis_type="architecture")
ask_gemini(prompt="Review @src/auth.py for injection risks")     # @file, @src/*.py, @src/**/*.ts, @.
ask_gemini(prompt="And how do I fix it?", continuation_id="…")   # follow-up with memory
ask_gemini(prompt="Long project kickoff", mode="cloud", title="Arch review")   # resumable for 55 days
```

---

## Models

Every tool asks for a **category**, and the registry resolves it at runtime to the newest model your key can use:

| Alias / category | Resolves today to | Notes |
|------------------|-------------------|-------|
| `pro` | `gemini-4-argon` | Flagship reasoning, 1M context, thinking low/medium/high |
| `flash` / `fast` | `gemini-3.8-flash` | Default for search, vision, RAG |
| `flash-lite` | `gemini-3.5-flash-lite` | Cheapest, highest throughput |
| image `pro` / `flash` / `lite` | Nano Banana Pro / 2.1 / 2 Lite | |
| video | `gemini-omni-1.1-flash` | |
| TTS `flash` / `lite` | Gemini 3.8 Flash TTS / Flash-Lite TTS | |
| music `full` / `clip` | `lyria-3.5` / `lyria-3-clip-preview` | |

Ranking: a newer naming scheme beats an older one (Gemini 4 codenames, Nano Banana), then higher version, then stable over preview. If Google stops *listing* a family while still serving it, known IDs are verified by name. Run `gemini_list_models` to see each resolution and where it came from, and set `GEMINI_MODEL_*` to pin one ([Configuration](#configuration)).

**Thinking**: `ask_gemini` takes `thinking_level` `auto` (default), `low`, `medium` or `high`. Gemini 3+ always reasons, so `auto` is not zero. `temperature` is accepted for compatibility but only reaches Gemini 2.x, Gemma and OpenRouter models: Google deprecated sampling parameters from Gemini 3.6.

**OpenRouter** (via `ask_model`): any ID from [openrouter.ai/models](https://openrouter.ai/models), for example `openai/gpt-4o`, `anthropic/claude-sonnet-5.5`, `x-ai/grok-4.7`, `deepseek/deepseek-v4-pro`, `meta-llama/llama-4-maverick`, `mistralai/mistral-large-2512`, `perplexity/sonar-pro` (web search with citations). Routing rules:

- `provider="auto"` (default): Gemini IDs and aliases go to the native API when `GEMINI_API_KEY` is set, otherwise to OpenRouter's `google/…` mirror. Any other ID goes to OpenRouter. No model means `pro`, or `OPENROUTER_DEFAULT_MODEL` without a Gemini key.
- `provider="openrouter"`: always OpenRouter. Gemini IDs and aliases become `google/<id>`; no model means `OPENROUTER_DEFAULT_MODEL`.
- `provider="gemini"`: native API only.
- An explicit Gemini ID is never swapped for Flash on a quota error; the aliases (`pro`, `flash`) are.

---

## Configuration

All settings are environment variables, passed with `-e` in `claude mcp add` or in the `env` block of your MCP config.

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | **required** | Google Gemini API key |
| `OPENROUTER_API_KEY` | — | Enables 400+ models in `ask_model` |
| `OPENROUTER_DEFAULT_MODEL` | `openai/gpt-4o` | Model `ask_model` uses with no model and either `provider="openrouter"` or no Gemini key |
| `OPENROUTER_TIMEOUT` | `120` | Seconds; raise for slow search models (`perplexity/sonar-deep-research`) |
| `GEMINI_MODEL_AUTODETECT` | `true` | `false` = static fallbacks instead of the live model list |
| `GEMINI_MODEL_PRO` · `_FLASH` · `_FLASH_LITE` | auto | Pin a text model (an explicit value always wins) |
| `GEMINI_MODEL_IMAGE_PRO` · `_IMAGE_FLASH` · `_IMAGE_LITE` | auto | Pin an image model |
| `GEMINI_MODEL_VIDEO` | auto | Pin the video model |
| `GEMINI_MODEL_TTS_FLASH` · `_TTS_LITE` · `GEMINI_MODEL_TRANSCRIBE` | auto | Pin speech models |
| `GEMINI_MODEL_MUSIC` · `_MUSIC_CLIP` | auto | Pin Lyria models |
| `GEMINI_MODEL_DEEP_RESEARCH` · `_DEEP_RESEARCH_MAX` · `GEMINI_MODEL_AGENT` | auto | Pin agent versions |
| `GEMINI_MODEL_EMBEDDING` · `GEMINI_MODEL_ROBOTICS` | auto | Pin embedding / Robotics ER models |
| `GEMINI_MAX_OUTPUT_TOKENS` | `65536` | Output budget per call (thinking and answer share it) |
| `GEMINI_SANDBOX_ROOT` | current dir* | The only folder the tools may read from and write to (`@file`, codebase analysis, uploads, `output_path`) |
| `GEMINI_SANDBOX_ENABLED` | `true` | Path sandboxing on/off. Credentials stay refused either way |
| `GEMINI_OUTPUT_DIR` | private temp folder | Where generated media and transcripts go when no `output_path` is given |
| `GEMINI_REQUEST_TIMEOUT` | `900` | Seconds before a single Gemini HTTP request is abandoned |
| `GEMINI_MAX_FILE_SIZE` | `102400` | Max bytes per file for `@file` and code tools |
| `GEMINI_LOG_DIR` | `~/.omni-ai-mcp` | Activity log and SQLite conversation memory |
| `GEMINI_LOG_FORMAT` | `text` | `text` or `json` |
| `GEMINI_ACTIVITY_LOG` | `true` | Activity logging on/off |
| `GEMINI_CONVERSATION_TTL_HOURS` · `_MAX_TURNS` | `3` · `50` | Local conversation expiry and length |
| `GEMINI_DISABLED_TOOLS` | — | Comma-separated tool names to hide |

\* The folder the client started the server in, unless that is `/` or your home folder (Claude Desktop does this): then `~/omni-ai-workspace`, created on first run. Set `GEMINI_SANDBOX_ROOT` to choose another folder.

---

## Claude Code plugin

Slash commands live in [`.claude/commands/`](https://github.com/marmyx77/omni-ai-mcp/tree/main/.claude/commands) and subagents in [`.claude/agents/`](https://github.com/marmyx77/omni-ai-mcp/tree/main/.claude/agents). They are active when Claude Code runs inside this repository, ship in the plugin zip, or can be copied globally:

```bash
cp .claude/commands/*.md ~/.claude/commands/ && cp .claude/agents/*.md ~/.claude/agents/
```

| Command | What it does |
|---------|--------------|
| `/gemini <question>` | Ask Gemini with full context |
| `/ask-model [model] <prompt>` | Ask any model (GPT, Claude, Llama, Grok, …) |
| `/cowork <task>` | Claude and Gemini on the same task, two independent perspectives |
| `/gemini-review <file>` | Code review |
| `/gemini-challenge <idea>` | Devil's advocate |
| `/gemini-analyze <path>` | Whole-codebase analysis |
| `/gemini-brainstorm <topic>` | Structured brainstorming |
| `/gemini-research <topic>` | Deep Research report |
| `/gemini-image <description>` | Infographics, diagrams, illustrations |
| `/gemini-illustrate <document>` | Add illustrations to a document |
| `/gemini-video <description>` | Generate or edit a short video |
| `/gemini-music <description>` | Generate a song or clip |
| `/gemini-watch <video or YouTube URL>` | Understand a video |
| `/gemini-models` | Show the models in use |
| `/setup` | Configure the server from inside Claude Code |

| Subagent | Triggered by | Uses |
|----------|--------------|------|
| `gemini-researcher` | "research X", "find sources on Y" | Deep Research, web search |
| `gemini-analyzer` | "audit this codebase", "review the architecture" | 1M-token analysis, review, challenge |
| `model-orchestrator` | "ask GPT", "compare models" | `ask_model` across providers |
| `cowork` | "second opinion", "verify with Gemini" | Claude + Gemini in parallel |

---

## Docker

The image runs the server over stdio as an unprivileged user and works with a read-only root filesystem.

```bash
docker build -t omni-ai-mcp .
claude mcp add omni-ai-mcp --scope user -- docker run -i --rm \
  -e GEMINI_API_KEY=YOUR_KEY \
  -v "$HOME/omni-workspace:/workspace" -v omni-ai-mcp-logs:/logs \
  --read-only --tmpfs /tmp omni-ai-mcp
```

Tools read and write files only under `/workspace`; logs and conversation memory live in the `/logs` volume. [`docker-compose.yml`](https://github.com/marmyx77/omni-ai-mcp/blob/main/docker-compose.yml) builds the same image with these limits.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Server not listed or not connected | `claude mcp list`; re-run the install command; restart Claude Code (running sessions keep the old server in memory) |
| `429 … monthly spending cap` | Your Google AI Studio project hit its spend cap: raise it at [ai.studio/spend](https://ai.studio/spend). Listing models still works, generation does not |
| `429 … rate limit` on `pro` | With an alias (`pro`), the server retries on Flash automatically; an explicit model ID is not swapped. For sustained work pin `GEMINI_MODEL_PRO` to a cheaper model or raise your quota |
| `Access denied: path is outside allowed directory` | The file is outside the workspace. Move it into the folder Claude Code runs in, or set `GEMINI_SANDBOX_ROOT` to the folder the tools may use |
| `Access denied: … is protected` | Credentials (`~/.ssh`, `.env`, keys, `~/.claude.json`, cloud CLI configs) are never read or written, by design |
| Video, music or research timed out | They keep running at Google: call the tool again with `retrieve_id` (video, music) or `continuation_id` and an empty query/task (Deep Research, agent) |
| Video edit of an uploaded clip refused | Not available in the EEA, Switzerland and the UK; edit a generated clip via `continuation_id` instead |
| A model "is not found" | Run `gemini_list_models`; remove stale `GEMINI_MODEL_*` pins; errors name the model and the package version that answered |
| OpenRouter error | Rate limits, 503 and connection errors are retried twice. Otherwise check `OPENROUTER_API_KEY` credit and the exact ID with `gemini_list_models(include_openrouter=True)` |
| Update the API key | `claude mcp remove omni-ai-mcp -s user`, then run the install command again |

---

## Costs

You pay Google and OpenRouter directly; this server adds nothing. Gemini prices change often, so check [ai.google.dev/pricing](https://ai.google.dev/gemini-api/docs/pricing) and [openrouter.ai/models](https://openrouter.ai/models). Snapshot of the text models, per million tokens (input / output), as published on 2026-10-25:

| Model | Price |
|-------|-------|
| Gemini 4 Argon | $2 / $10 until 2026-11-30, then $4 / $20 |
| Gemini 3.8 Flash | $0.75 / $3.75 until 2026-12-31, then $1.50 / $7.50 |
| Gemini 3.5 Flash-Lite | $0.30 / $2.50 |

Video, music, images, speech, Deep Research and the agent are priced per output or per run: start small (`resolution="360p"`, `model="clip"`, `depth="standard"`).

---

## Development

```bash
git clone https://github.com/marmyx77/omni-ai-mcp.git && cd omni-ai-mcp
python3 -m pip install -e ".[dev]"
python3 -m pytest tests/ -q                                   # hermetic: no API key, no network
GEMINI_API_KEY=… python3 scripts/smoke_live.py                # one real call per tool (cheap set)
GEMINI_API_KEY=… python3 scripts/smoke_live.py --expensive    # + video, music, research, agent
node virgilio/bin/cli.mjs check --config virgilio.config.json  # docs ↔ reality gate (CI-enforced)
```

How the code is organised, how to add a tool and how releases work: [CONTRIBUTING.md](https://github.com/marmyx77/omni-ai-mcp/blob/main/CONTRIBUTING.md) and [CLAUDE.md](https://github.com/marmyx77/omni-ai-mcp/blob/main/CLAUDE.md).

```
app/
├── server.py          FastMCP server: 28 @mcp.tool() registrations
├── core/              config, structured logging, security (sandbox, secrets, safe writes)
├── services/          Gemini client, model registry, Interactions helpers, OpenRouter, SQLite memory
├── tools/             text/ · code/ · media/ · web/ · rag/
├── schemas/           Pydantic input validation
└── utils/             @file expansion, token estimates
scripts/               install_release.sh · smoke_live.py · bump_version.sh · build_dxt.sh · build_plugin.sh
tests/                 unit/ and integration/ (hermetic)
```

---

## Security

- Every path a tool reads, uploads or writes is resolved (symlinks included) and must stay inside `GEMINI_SANDBOX_ROOT`. That covers `@file` references, codebase analysis, media inputs and `output_path`
- Credentials and keys (`~/.ssh`, `.env`, `*.pem`, `~/.claude.json`, cloud CLI configs…) are refused even with the sandbox off
- Outputs need an allowed extension and never go through a symlink; without `output_path` they land in a private folder with random names, which the tools can read back
- No tool writes agent instructions or hooks (`CLAUDE.md`, `.mcp.json`, `.claude/`, `.git/`, `.vscode/`…)
- Media downloads send the API key only to Google hosts over HTTPS, never across a redirect
- API keys and tokens are masked in logs and error messages; the installers write `~/.claude.json` with mode 600
- LLM-generated XML is sanitized before parsing; tool inputs are validated with Pydantic
- Voice replication requires the speaker's recorded consent, which Google verifies

Report vulnerabilities privately as described in [SECURITY.md](https://github.com/marmyx77/omni-ai-mcp/blob/main/SECURITY.md).

---

## Contributing and license

Contributions are welcome: read [CONTRIBUTING.md](https://github.com/marmyx77/omni-ai-mcp/blob/main/CONTRIBUTING.md) and the [Code of Conduct](https://github.com/marmyx77/omni-ai-mcp/blob/main/CODE_OF_CONDUCT.md), then open an issue or a pull request.

MIT — see [LICENSE](https://github.com/marmyx77/omni-ai-mcp/blob/main/LICENSE).
