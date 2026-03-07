#!/usr/bin/env bash
# Build .dxt Desktop Extension bundle for Claude Desktop
# Format: https://github.com/anthropics/dxt
set -euo pipefail

BUILD_DIR="build_dxt"
VERSION=$(python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    print(tomllib.load(f)['project']['version'])
" 2>/dev/null || grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
OUTPUT="omni-ai-mcp-v${VERSION}.dxt"

echo "Building .dxt extension v${VERSION}..."

# Clean previous build
rm -rf "$BUILD_DIR" "$OUTPUT"
mkdir -p "$BUILD_DIR/server" "$BUILD_DIR/lib"

# Copy server code
cp run.py "$BUILD_DIR/server/"
cp -r app/ "$BUILD_DIR/server/app/"

# Copy manifest and inject version from pyproject.toml (source of truth)
# This ensures the .dxt always has the correct version even if manifest.json
# was not updated manually. Use bump_version.sh to keep them in sync.
cp manifest.json "$BUILD_DIR/"
if [[ "$(uname -s)" == "Darwin" ]]; then
  sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$BUILD_DIR/manifest.json"
else
  sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$BUILD_DIR/manifest.json"
fi

# Copy icon if present
[ -f icon.png ] && cp icon.png "$BUILD_DIR/"

# Bundle Python dependencies into lib/
echo "Installing dependencies into lib/..."
pip3 install --target "$BUILD_DIR/lib" --quiet \
  "google-genai>=1.55.0" \
  "mcp[cli]>=1.0.0" \
  "pydantic>=2.0.0" \
  "defusedxml>=0.7.1" \
  "filelock>=3.0.0"

# Remove unnecessary files from lib/ to reduce size
find "$BUILD_DIR/lib" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR/lib" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR/lib" -name "*.pyc" -delete 2>/dev/null || true

# Pack into .dxt
if command -v dxt &>/dev/null; then
  dxt pack "$BUILD_DIR" "$OUTPUT"
  echo "Packed with dxt CLI."
else
  # Fallback: zip manually (.dxt is a zip archive)
  (cd "$BUILD_DIR" && zip -r "../$OUTPUT" . -x "*.pyc" -x "*/__pycache__/*")
  echo "Packed with zip (dxt CLI not found — install with: npm install -g @anthropic-ai/dxt)"
fi

# Also produce a .zip copy for Claude Desktop versions that show "upload zip" dialog
ZIP_OUTPUT="omni-ai-mcp-v${VERSION}.zip"
cp "$OUTPUT" "$ZIP_OUTPUT"

# Cleanup
rm -rf "$BUILD_DIR"

echo ""
echo "Done:"
echo "  $OUTPUT     — install by double-clicking (Claude Desktop with .dxt support)"
echo "  $ZIP_OUTPUT — upload via 'Install from zip' dialog in Claude Desktop"
