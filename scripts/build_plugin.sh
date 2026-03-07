#!/usr/bin/env bash
# Build Claude Code plugin zip (.claude-plugin format)
# Format: https://code.claude.com/docs/en/plugins-reference
#
# Structure of the resulting zip:
#   .claude-plugin/plugin.json   ← plugin manifest (required)
#   .mcp.json                    ← MCP server config (uvx omni-ai-mcp from PyPI)
#   commands/                    ← slash commands
#   agents/                      ← subagents
#
# Installation:
#   Download the zip and install via Claude Code: /install-plugin <path>
#   Or drag the zip into Claude Code's plugin dialog
#
# Prerequisite for end users: uv must be installed
#   macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
#   Windows:     powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
#
# After install, set GEMINI_API_KEY in your shell (OPENROUTER_API_KEY optional):
#   export GEMINI_API_KEY=your_key_here
set -euo pipefail

BUILD_DIR="build_plugin"
VERSION=$(python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    print(tomllib.load(f)['project']['version'])
" 2>/dev/null || grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
OUTPUT="omni-ai-mcp-plugin-v${VERSION}.zip"

echo "Building Claude Code plugin v${VERSION}..."

# Clean previous build
rm -rf "$BUILD_DIR" "$OUTPUT"
mkdir -p "$BUILD_DIR"

# Copy plugin manifest
mkdir -p "$BUILD_DIR/.claude-plugin"
cp .claude-plugin/plugin.json "$BUILD_DIR/.claude-plugin/plugin.json"

# Inject current version into plugin.json
if [[ "$(uname -s)" == "Darwin" ]]; then
  sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$BUILD_DIR/.claude-plugin/plugin.json"
else
  sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$BUILD_DIR/.claude-plugin/plugin.json"
fi

# Generate .mcp.json — MCP server config (uses uvx to pull from PyPI)
cat > "$BUILD_DIR/.mcp.json" <<'JSON'
{
  "mcpServers": {
    "omni-ai-mcp": {
      "command": "uvx",
      "args": ["omni-ai-mcp"],
      "env": {
        "GEMINI_API_KEY": "${GEMINI_API_KEY}",
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    }
  }
}
JSON

# Copy commands (from .claude/commands/ → commands/)
mkdir -p "$BUILD_DIR/commands"
cp .claude/commands/*.md "$BUILD_DIR/commands/"

# Copy agents (from .claude/agents/ → agents/)
mkdir -p "$BUILD_DIR/agents"
cp .claude/agents/*.md "$BUILD_DIR/agents/"

# Build zip
(cd "$BUILD_DIR" && zip -r "../$OUTPUT" . -x "*.DS_Store")

# Cleanup
rm -rf "$BUILD_DIR"

FILE_COUNT=$(unzip -l "$OUTPUT" | tail -1 | awk '{print $2}')
echo ""
echo "Done: $OUTPUT ($FILE_COUNT files)"
echo ""
echo "Install in Claude Code:"
echo "  /install-plugin $OUTPUT"
echo "  (or drag the zip into Claude Code's plugin dialog)"
echo ""
echo "Required: set GEMINI_API_KEY in your shell before using."
echo "Optional: set OPENROUTER_API_KEY for 400+ additional models."
