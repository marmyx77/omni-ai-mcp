# Security Policy

## Supported versions

Only the latest minor release line receives fixes. Releases are cut often and upgrading is a single command (`uv cache clean omni-ai-mcp`, `pip install -U omni-ai-mcp`, or `scripts/install_release.sh`).

| Version | Supported |
|---------|-----------|
| latest 4.x minor ([PyPI](https://pypi.org/project/omni-ai-mcp/)) | :white_check_mark: |
| anything older | :x: upgrade |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub: **Security → Report a vulnerability** on [this repository](https://github.com/marmyx77/omni-ai-mcp/security/advisories/new). Include the version (`python -c "import app; print(app.__version__)"`), what an attacker can do, and the steps or input that trigger it. You will get an acknowledgement within a few days; fixes ship as a patch release with a GitHub Security Advisory crediting you, unless you prefer otherwise.

## Threat model in short

omni-ai-mcp runs locally with your permissions and is driven by an LLM (Claude). Tool arguments can therefore be influenced by content the model reads (web pages, documents, transcripts). The server is built so that a misled model cannot reach outside the sandbox or leak secrets through the server itself.

## Protections in the code

| Area | What it does | Where |
|------|--------------|-------|
| Path sandboxing | Every file path is resolved (symlinks included) and must stay inside `GEMINI_SANDBOX_ROOT` | `app/core/security.py` `validate_path` |
| Safe reads | Size is checked with `fstat()` on the open descriptor (no TOCTOU race); binary files and files over `GEMINI_MAX_FILE_SIZE` are refused | `secure_read_file`, `check_file_size` |
| Safe writes | Atomic writes with a timestamped backup, cross-platform file locking | `SafeFileWriter`, `file_lock` |
| Secret masking | 17 patterns (Google, AWS, GitHub, OpenAI, Anthropic, Slack, JWT, Bearer, PEM keys, URL passwords, …) masked in logs, with a regex timeout against ReDoS | `SecretsSanitizer` |
| Generated code | LLM XML is sanitized before parsing; only `create`/`modify`/`delete` actions; `..`, absolute and `~` paths rejected; dry-run mode | `app/tools/code/generate_code.py` |
| Resource limits | 5 MB total input for codebase analysis; prompt size checks | `analyze_codebase.py`, `utils/tokens.py` |
| Input validation | Pydantic v2 schemas on tool inputs | `app/schemas/inputs.py` |
| Plugins | Plugin directories that are world-writable are refused | `app/tools/registry.py` |
| Conversation store | SQLite database created with owner-only permissions (`0700` dir, `0600` file) in `GEMINI_LOG_DIR` | `app/services/persistence.py` |
| Container | Non-root user, read-only root filesystem supported, writable only `/workspace`, `/logs`, `/tmp` | `Dockerfile`, `docker-compose.yml` |

Upstream safeguards also apply: Google's safety filters on prompts and generated media, SynthID watermarks on generated video and audio, and server-side consent verification for voice replication.

## Handling your API keys

- Pass keys as environment variables (`claude mcp add … -e GEMINI_API_KEY=…`), never in prompts or committed files.
- Keys live in your MCP client config (for Claude Code, `~/.claude.json`): keep that file private.
- Set a spending cap on your Google AI Studio project ([ai.studio/spend](https://ai.studio/spend)) and a credit limit on OpenRouter: video, music, Deep Research and agent runs are billed per run.
- Rotate a key immediately if it was ever pasted into a chat, a log or a commit.

## What this project does not do

- It does not proxy or store your traffic: requests go directly from your machine to Google or OpenRouter.
- It sends no telemetry. The activity log stays in `GEMINI_LOG_DIR` and can be disabled with `GEMINI_ACTIVITY_LOG=false`.
