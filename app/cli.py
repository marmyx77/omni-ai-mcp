"""
omni-ai-mcp CLI — Setup Wizard

Configures Claude Code to use omni-ai-mcp by updating ~/.claude.json.
Run via: omni-ai-mcp-setup
"""

import json
import os
import sys
from pathlib import Path


def _read_json(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _write_json(path: Path, data: dict) -> None:
    """Atomic, owner-only (0600) write: the file holds API keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-omni-{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    print(f"  Written: {path} (mode 600)")


def setup_claude() -> None:
    """Interactive setup wizard — configures claude.json for omni-ai-mcp."""

    from . import __version__
    print(f"\nomni-ai-mcp v{__version__} — Setup Wizard")
    print("=" * 40)

    # Find omni-ai-mcp entry point
    server_cmd = sys.executable
    server_module = "-m app.server"

    # Try to find the installed run script
    omni_ai_mcp_bin = Path(sys.prefix) / "bin" / "omni-ai-mcp"
    if not omni_ai_mcp_bin.exists():
        omni_ai_mcp_bin = Path(sys.prefix) / "Scripts" / "omni-ai-mcp.exe"  # Windows

    # Get API key
    existing_key = os.environ.get("GEMINI_API_KEY", "")
    if existing_key:
        print(f"\nGEMINI_API_KEY detected in environment.")
        api_key = existing_key
    else:
        api_key = input("\nEnter your Google Gemini API key (from https://ai.google.dev): ").strip()
        if not api_key:
            print("Error: API key is required.")
            sys.exit(1)

    # Optional OpenRouter key
    openrouter_key = input(
        "\nEnter OPENROUTER_API_KEY for 400+ models (optional, press Enter to skip): "
    ).strip()

    # Build MCP server config
    env_vars: dict = {"GEMINI_API_KEY": api_key}
    if openrouter_key:
        env_vars["OPENROUTER_API_KEY"] = openrouter_key

    if omni_ai_mcp_bin.exists():
        server_config = {
            "command": str(omni_ai_mcp_bin),
            "env": env_vars,
        }
    else:
        server_config = {
            "command": server_cmd,
            "args": ["-m", "app.server"],
            "env": env_vars,
        }

    # Update ~/.claude.json
    claude_json = Path.home() / ".claude.json"
    data = _read_json(claude_json)

    if "mcpServers" not in data:
        data["mcpServers"] = {}

    data["mcpServers"]["omni-ai-mcp"] = server_config

    print("\nWriting configuration...")
    _write_json(claude_json, data)

    print("\nSetup complete!")
    print("Restart Claude Code to activate omni-ai-mcp.")
    print("\nTools: text and reasoning (ask_gemini, ask_model, code review, brainstorm, challenge),")
    print("  code (codebase analysis, generation, Antigravity agent), research (web search, Deep Research),")
    print("  media (images, video, music, TTS and voices, transcription, image/video analysis),")
    print("  embeddings, RAG and conversations: 28 tools. List them in Claude Code with /mcp.")


if __name__ == "__main__":
    setup_claude()
