#!/usr/bin/env bash
# Bump version across all project files in one command.
#
# Usage:
#   bash scripts/bump_version.sh 4.1.0
#
# Files updated:
#   pyproject.toml        — [project] version
#   app/__init__.py       — __version__
#   app/core/config.py    — version field in Config
#   manifest.json         — "version" (DXT plugin manifest)
#
# After running this script:
#   1. Add release notes to CHANGELOG.md
#   2. git add -A && git commit -m "chore: bump version to <new>"
#   3. git tag v<new> && git push origin main v<new>
#      → GitHub Actions will publish to PyPI and build .dxt automatically

set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: bash scripts/bump_version.sh <new-version>"
  echo "Example: bash scripts/bump_version.sh 4.1.0"
  exit 1
fi

NEW_VERSION="$1"

# Validate semver format
if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: version must be in X.Y.Z format (got: $NEW_VERSION)"
  exit 1
fi

# Detect current version from pyproject.toml (source of truth)
CURRENT_VERSION=$(python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    print(tomllib.load(f)['project']['version'])
")

if [ "$CURRENT_VERSION" = "$NEW_VERSION" ]; then
  echo "Already at version $NEW_VERSION — nothing to do."
  exit 0
fi

echo "Bumping: $CURRENT_VERSION → $NEW_VERSION"
echo ""

# macOS sed requires '' after -i; Linux sed doesn't — detect platform
SED_INPLACE=(-i '')
if [[ "$(uname -s)" != "Darwin" ]]; then
  SED_INPLACE=(-i)
fi

# 1. pyproject.toml
sed "${SED_INPLACE[@]}" \
  "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" \
  pyproject.toml
echo "  [ok] pyproject.toml"

# 2. app/__init__.py
sed "${SED_INPLACE[@]}" \
  "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" \
  app/__init__.py
echo "  [ok] app/__init__.py"

# 3. app/core/config.py
sed "${SED_INPLACE[@]}" \
  "s/version: str = \"$CURRENT_VERSION\"/version: str = \"$NEW_VERSION\"/" \
  app/core/config.py
echo "  [ok] app/core/config.py"

# 4. manifest.json (DXT plugin)
sed "${SED_INPLACE[@]}" \
  "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" \
  manifest.json
echo "  [ok] manifest.json"

echo ""
echo "All files updated to v$NEW_VERSION."
echo ""
echo "Next steps:"
echo "  1. Add release notes to CHANGELOG.md"
echo "  2. git add -A && git commit -m 'chore: bump version to $NEW_VERSION'"
echo "  3. git tag v$NEW_VERSION && git push origin main v$NEW_VERSION"
echo "     → PyPI publish + .dxt build start automatically"
