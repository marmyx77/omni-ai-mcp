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

omni-ai-mcp runs locally with your permissions and is driven by an LLM (Claude). Tool arguments can therefore be influenced by content the model reads (web pages, documents, transcripts). The server is built so that a misled model cannot make it read files outside the workspace, send credentials to Google, or write outside the workspace.

Files a tool reads are **sent to Google** (or to OpenRouter) as part of the request. That is the purpose of the tools, so the workspace boundary is what keeps the rest of your disk out of those requests. Before 4.8.2, `@file` references and `gemini_analyze_codebase` did not enforce it: upgrade.

## Protections in the code

| Area | What it does | Where |
|------|--------------|-------|
| Workspace boundary | Every path a tool reads, uploads or writes is resolved (symlinks included) and must stay inside `GEMINI_SANDBOX_ROOT`: `@file` references and their globs, codebase analysis, media and document inputs, RAG uploads, `output_path` | `app/core/security.py` `validate_path`, `safe_input_path`, `safe_output_path` |
| Default workspace | Without `GEMINI_SANDBOX_ROOT`, the folder the client started the server in; if that is `/` or your home folder (Claude Desktop), `~/omni-ai-workspace` instead of the whole disk | `app/core/config.py` |
| Credentials deny-list | `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.kube`, `~/.docker`, `~/.claude`, `~/.claude.json`, `.env*`, `*.pem`, `*.key`, `id_*` keys, `.netrc`, `.npmrc`, `.pypirc`, cloud CLI configs and similar are refused **even with the sandbox disabled**, whatever the letter case (macOS ignores it), and hidden from directory listings | `sensitive_reason` |
| Outputs | An allowed extension is mandatory (an output can never become `~/.zshrc` or a LaunchAgent), no writing through symlinks; without `output_path`, files go to a private `0700` folder you own, with unpredictable names (`GEMINI_OUTPUT_DIR` to change). That folder is readable by the tools too, so a generated image can be edited next | `safe_output_path`, `default_output_path` |
| Write-protected project files | No tool, `gemini_generate_code` included, writes agent instructions or hooks: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.mcp.json`, or anything under `.git/`, `.claude/`, `.vscode/`, `.idea/`, `.husky/`, `.cursor/`. A prompt-injected output path cannot plant persistent instructions or a commit hook | `write_protected_reason` |
| Globs | The fixed part of a glob is checked before the walk, so `@/**/*` is refused instead of scanning the disk | `glob_root_allowed` |
| Media downloads | The API key is sent only to Google hosts over HTTPS; redirects are followed only to Google hosts and without the key | `app/services/interactions.py` `_download_uri` |
| Safe reads | Size is checked with `fstat()` on the open descriptor (no TOCTOU race); binary files and files over `GEMINI_MAX_FILE_SIZE` are refused | `secure_read_file`, `check_file_size` |
| Safe writes | Atomic writes with a timestamped backup, cross-platform file locking | `SafeFileWriter`, `file_lock` |
| Secret masking | 19 patterns (Google, AWS, GitHub, OpenAI, OpenRouter, Anthropic, Slack, JWT, Bearer, PEM keys, URL passwords, …) masked in logs and in upstream error messages, with a regex timeout against ReDoS | `SecretsSanitizer` |
| Generated code | LLM XML is sanitized before parsing; only `create`/`modify`/`delete` actions; `..`, absolute and `~` paths rejected; dry-run mode | `app/tools/code/generate_code.py` |
| Resource limits | 5 MB total input for codebase analysis; prompt size checks | `analyze_codebase.py`, `utils/tokens.py` |
| Input validation | Pydantic v2 schemas on tool inputs | `app/schemas/inputs.py` |
| Plugins | Plugin directories that are world-writable are refused | `app/tools/registry.py` |
| Conversation store | SQLite database created with owner-only permissions (`0700` dir, `0600` file) in `GEMINI_LOG_DIR` | `app/services/persistence.py` |
| Container | Non-root user, read-only root filesystem supported, writable only `/workspace`, `/logs`, `/tmp` | `Dockerfile`, `docker-compose.yml` |
| Release pipeline | Actions pinned to commit SHAs; read-only token by default; the PyPI publish job holds only the OIDC token, the release job only `contents: write` | `.github/workflows/` |

Upstream safeguards also apply: Google's safety filters on prompts and generated media, SynthID watermarks on generated video and audio, and server-side consent verification for voice replication.

## Handling your API keys

- Pass keys as environment variables, never in prompts or committed files. `setup.sh` and `scripts/install_release.sh` take them from the environment and write them into `~/.claude.json` directly, so they never show up in the process list.
- Keys live in your MCP client config (for Claude Code, `~/.claude.json`). The installers and `omni-ai-mcp-setup` write it with mode `600` and keep their backups owner-only; if you edit it by hand, run `chmod 600 ~/.claude.json`.
- Set a spending cap on your Google AI Studio project ([ai.studio/spend](https://ai.studio/spend)) and a credit limit on OpenRouter: video, music, Deep Research and agent runs are billed per run.
- Rotate a key immediately if it was ever pasted into a chat, a log or a commit.

## What this project does not do

- It does not proxy or store your traffic: requests go directly from your machine to Google or OpenRouter.
- It sends no telemetry. The activity log stays in `GEMINI_LOG_DIR` and can be disabled with `GEMINI_ACTIVITY_LOG=false`.
