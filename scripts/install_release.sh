#!/usr/bin/env bash
# Install (or update) omni-ai-mcp on a machine from a GitHub release tag, and
# point Claude Code at it. Idempotent: run it again with a newer tag to update.
#
#   bash scripts/install_release.sh            # latest tag on GitHub
#   bash scripts/install_release.sh v4.6.5     # a specific tag
#   bash scripts/install_release.sh --status   # installed vs latest, no changes
#
# What it does:
#   1. resolves the tag (default: highest vX.Y.Z on GitHub)
#   2. creates/reuses a venv in $OMNI_INSTALL_DIR (default ~/.claude-mcp-servers/omni-ai-mcp)
#   3. pip-installs the package FROM GITHUB at that tag (no local checkout, no editable)
#   4. writes mcpServers.omni-ai-mcp in ~/.claude.json: <venv>/bin/python3 -m app.server,
#      keeping the env block already there (API keys) — backup taken first
#
# Dev machines keep their editable checkout; this is for execution nodes.

set -euo pipefail

REPO="${OMNI_REPO:-https://github.com/marmyx77/omni-ai-mcp}"
INSTALL_DIR="${OMNI_INSTALL_DIR:-$HOME/.claude-mcp-servers/omni-ai-mcp}"
VENV="$INSTALL_DIR/venv"
PYTHON="${OMNI_PYTHON:-python3}"
CLAUDE_JSON="$HOME/.claude.json"

latest_tag() {
  git ls-remote --tags --refs "$REPO" 2>/dev/null \
    | awk -F/ '{print $NF}' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1
}

installed_version() {
  if [ -x "$VENV/bin/python3" ]; then
    (cd / && "$VENV/bin/python3" -c "import app; print(app.__version__)" 2>/dev/null) || echo "none"
  else
    echo "none"
  fi
}

if [ "${1:-}" = "--status" ]; then
  echo "installed: $(installed_version)   latest tag: $(latest_tag)   venv: $VENV"
  exit 0
fi

TAG="${1:-$(latest_tag)}"
[ -n "$TAG" ] || { echo "Cannot resolve a tag from $REPO" >&2; exit 1; }
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Tag must look like vX.Y.Z (got: $TAG)" >&2; exit 1; }

echo "omni-ai-mcp: installing $TAG from $REPO"
echo "  before: $(installed_version)"

mkdir -p "$INSTALL_DIR"
if [ ! -x "$VENV/bin/python3" ]; then
  "$PYTHON" -m venv "$VENV"
  echo "  venv created with $("$VENV/bin/python3" --version)"
fi

"$VENV/bin/python3" -m pip install --quiet --upgrade pip
"$VENV/bin/python3" -m pip install --quiet --upgrade "omni-ai-mcp @ git+${REPO}@${TAG}"
"$VENV/bin/python3" -m pip check >/dev/null || { echo "pip check failed" >&2; exit 1; }

INSTALLED="$(installed_version)"
[ "v$INSTALLED" = "$TAG" ] || { echo "Installed $INSTALLED but expected $TAG" >&2; exit 1; }
echo "  after:  $INSTALLED"

# --- ~/.claude.json ---------------------------------------------------------
if [ -f "$CLAUDE_JSON" ]; then
  cp "$CLAUDE_JSON" "$CLAUDE_JSON.bak-$(date +%Y%m%d-%H%M%S)-omni-$TAG"
fi
VENV="$VENV" CLAUDE_JSON="$CLAUDE_JSON" "$VENV/bin/python3" - <<'PY'
import json, os
path = os.environ["CLAUDE_JSON"]
venv = os.environ["VENV"]
data = json.load(open(path)) if os.path.exists(path) else {}
servers = data.setdefault("mcpServers", {})
current = servers.get("omni-ai-mcp", {})
env = dict(current.get("env", {}))
if not env.get("GEMINI_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    env["GEMINI_API_KEY"] = os.environ["GEMINI_API_KEY"]
if not env.get("OPENROUTER_API_KEY") and os.environ.get("OPENROUTER_API_KEY"):
    env["OPENROUTER_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
servers["omni-ai-mcp"] = {
    "type": "stdio",
    "command": f"{venv}/bin/python3",
    "args": ["-m", "app.server"],
    "env": env,
}
json.dump(data, open(path, "w"), indent=2)
print("  ~/.claude.json: mcpServers.omni-ai-mcp ->", f"{venv}/bin/python3 -m app.server",
      "| env keys:", sorted(env.keys()))
if not env.get("GEMINI_API_KEY"):
    print("  WARNING: no GEMINI_API_KEY in env — set it in ~/.claude.json or export it and rerun")
PY

echo "Done. Restart Claude Code sessions on this machine (running servers keep the old code in memory)."
