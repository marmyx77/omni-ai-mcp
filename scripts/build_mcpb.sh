#!/usr/bin/env bash
# Build .mcpb bundle for Claude Desktop distribution
set -euo pipefail

BUNDLE_DIR="bundle"
OUTPUT="omni-ai-mcp.mcpb"

echo "Building .mcpb bundle..."

# Clean previous build
rm -rf "$BUNDLE_DIR" "$OUTPUT"
mkdir -p "$BUNDLE_DIR/lib"

# Bundle Python dependencies
pip install --target "$BUNDLE_DIR/lib" \
  "google-genai>=1.55.0" \
  "mcp[cli]>=1.0.0" \
  "pydantic>=2.0.0" \
  "defusedxml>=0.7.1" \
  "filelock>=3.0.0"

# Copy source code
cp -r app/ "$BUNDLE_DIR/app/"
cp manifest.json "$BUNDLE_DIR/"
cp run.py "$BUNDLE_DIR/" 2>/dev/null || true

# Try to pack with mcpb CLI if available
if command -v mcpb &>/dev/null; then
  mcpb pack "$BUNDLE_DIR" --output "$OUTPUT"
  echo "Bundle created: $OUTPUT"
else
  # Fallback: create zip with .mcpb extension
  (cd "$BUNDLE_DIR" && zip -r "../$OUTPUT" .)
  echo "Bundle created (zip fallback): $OUTPUT"
  echo "Note: install @anthropic-ai/mcpb for proper .mcpb format"
fi

# Cleanup
rm -rf "$BUNDLE_DIR"
echo "Done."
