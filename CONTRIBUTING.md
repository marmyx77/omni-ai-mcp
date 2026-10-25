# Contributing to omni-ai-mcp

Thanks for helping. Bug reports, model updates, docs fixes and new tools are all welcome. By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Quick start

```bash
git clone https://github.com/marmyx77/omni-ai-mcp.git && cd omni-ai-mcp
python3 -m pip install -e ".[dev]"          # Python 3.10+
python3 -m pytest tests/ -q                  # must pass, no API key needed
```

To try your changes inside Claude Code, run `./setup.sh YOUR_GEMINI_KEY`: it installs the checkout in editable mode and registers it, so every edit is live after restarting Claude Code.

## Ways to help

- **Report a bug** with the [bug template](https://github.com/marmyx77/omni-ai-mcp/issues/new?template=bug_report.yml): version, tool, arguments, full error. The output of `gemini_list_models` helps whenever a model is involved.
- **Propose a feature** with the [feature template](https://github.com/marmyx77/omni-ai-mcp/issues/new?template=feature_request.yml).
- **Keep up with Google**: new Gemini models usually need no code, because the registry detects them. A new naming scheme or a new model family does: add or extend a category in `app/services/model_registry.py` (see below).
- **Security issues**: never in public issues; follow [SECURITY.md](SECURITY.md).

## Project layout

```
app/
├── server.py            FastMCP registrations: one @mcp.tool() wrapper per tool
├── core/                config.py (env vars), logging.py, security.py
├── services/
│   ├── gemini.py        Gemini client, lazy model maps (MODELS, IMAGE_MODELS…), generate_with_fallback
│   ├── model_registry.py runtime model discovery: CATEGORY_SPECS, ranking, probing
│   ├── interactions.py  Interactions API helpers: file inputs, polling, outputs, media saving
│   ├── openrouter.py    OpenRouter client
│   └── persistence.py   SQLite conversation memory
├── tools/<domain>/      tool implementations (text, code, media, web, rag), registered with @tool
├── schemas/inputs.py    Pydantic input models
└── utils/               @file expansion, token estimates
```

## Rules of the codebase

- **Never hardcode a model ID in a tool.** Ask the registry for a category: `MODELS["pro"]`, `IMAGE_MODELS["flash"]`, `model_registry.resolve("music")`. New family → new entry in `CATEGORY_SPECS` with anchored patterns, fallbacks, an env var and a config default.
- **Don't send sampling parameters to Gemini 3+.** Use `legacy_sampling(model_id, temperature)`; budgets come from `config.max_output_tokens`.
- **Interactions API tools** (video, music, TTS, agents, video analysis) use `app/services/interactions.py`: `file_block` for inputs, `run`/`wait` for execution (background + polling), `output_text`/`output_media`/`save_media` for results. Long jobs must offer a way to retrieve the result after a timeout.
- **Files go through the sandbox** (`validate_path`, `secure_read_file`, `secure_write_file`).
- **Errors are returned, not raised**, as a short message that names what failed and what to do.
- Python 3.10+, type hints on public functions, Google-style docstrings, small functions, immutable data where practical.

## Adding a tool

1. Create `app/tools/<domain>/my_tool.py` with a JSON schema and a function decorated with `@tool(name="gemini_my_tool", description=..., input_schema=...)`. Put request building in a pure function (`build_*_request`) so tests can check it without the network.
2. Export it from `app/tools/<domain>/__init__.py`.
3. Add the `@mcp.tool()` wrapper in `app/server.py`, with an `Args:` docstring (that is what MCP clients show).
4. Write unit tests in `tests/unit/`. For Interactions requests, validate them against the SDK schema (`google.genai._gaos.google_genai.interactions.CreateModelInteraction.model_validate`), as `tests/unit/test_media_tools_v48.py` does.
5. Update the tool count and tables (README, CLAUDE.md «Available Tools», `tests/integration/test_fastmcp_server.py`) and add a check to `scripts/smoke_live.py`.

## Before opening a pull request

```bash
python3 -m pytest tests/ -q
node virgilio/bin/cli.mjs check --config virgilio.config.json   # docs ↔ reality gate, runs in CI
GEMINI_API_KEY=… python3 scripts/smoke_live.py --only <checks you touched>   # if you changed live behaviour
```

- One topic per PR, with a description of *why* and how you verified it (the PR template asks for it).
- Add an entry under a new version heading in [CHANGELOG.md](CHANGELOG.md) for user-visible changes.
- Don't bump versions or tag: maintainers do that at release time with `scripts/bump_version.sh`.
- `main` is protected: PRs need the `test (3.11)`, `test (3.12)` and `docs-gate` checks green.

## Documentation rules

Docs are checked against reality by [virgilio](DOC_GOVERNANCE.md): counts, banned stale phrases and links fail CI. Each fact (version, tool count, test-file counts, release status) lives in one owner document; elsewhere, link to it. Don't write test-pass counts or model prices you haven't checked.
