#!/usr/bin/env bash
# Build .dxt Desktop Extension bundle for Claude Desktop
# Format: https://github.com/anthropics/dxt
#
# Strategy: uses uvx (uv) to run the package from PyPI at runtime.
# No Python dependencies are bundled — the bundle only contains manifest.json.
# This keeps the file count well under Claude Desktop's 200-file limit.
#
# Prerequisite for end users: uv must be installed.
#   macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
#   Windows:     powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
set -euo pipefail

BUILD_DIR="build_dxt"
VERSION=$(python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    print(tomllib.load(f)['project']['version'])
" 2>/dev/null || grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
OUTPUT="omni-ai-mcp-v${VERSION}.dxt"
ZIP_OUTPUT="omni-ai-mcp-v${VERSION}.zip"

echo "Building .dxt extension v${VERSION} (uvx/PyPI strategy)..."

# Clean previous build
rm -rf "$BUILD_DIR" "$OUTPUT" "$ZIP_OUTPUT"
mkdir -p "$BUILD_DIR"

# Copy manifest and inject version from pyproject.toml (source of truth)
cp manifest.json "$BUILD_DIR/"
if [[ "$(uname -s)" == "Darwin" ]]; then
  sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$BUILD_DIR/manifest.json"
else
  sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$BUILD_DIR/manifest.json"
fi

# Copy icon if present
[ -f icon.png ] && cp icon.png "$BUILD_DIR/"

# Pack into .dxt (just manifest + optional icon — no bundled deps)
if command -v dxt &>/dev/null; then
  dxt pack "$BUILD_DIR" "$OUTPUT"
  echo "Packed with dxt CLI."
else
  (cd "$BUILD_DIR" && zip -r "../$OUTPUT" .)
  echo "Packed with zip (dxt CLI not found — install with: npm install -g @anthropic-ai/dxt)"
fi

# Also produce .zip copy for Claude Desktop versions that show "upload zip" dialog
cp "$OUTPUT" "$ZIP_OUTPUT"

# Cleanup
rm -rf "$BUILD_DIR"

echo ""
echo "Done ($(du -sh "$OUTPUT" | cut -f1) — no bundled deps, uses uvx from PyPI):"
echo "  $OUTPUT     — install by double-clicking (Claude Desktop with .dxt support)"
echo "  $ZIP_OUTPUT — upload via 'Install from zip' dialog in Claude Desktop"
echo ""
echo "Requirement: end users need uv installed."
echo "  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh"
