#!/usr/bin/env bash
# Install omni-ai-mcp from this source checkout and register it in Claude Code.
#
#   GEMINI_API_KEY=... [OPENROUTER_API_KEY=...] ./setup.sh     (preferred: keys stay out of shell history)
#   ./setup.sh GEMINI_API_KEY [OPENROUTER_API_KEY]
#
# What it does:
#   1. picks a Python >= 3.10 (OMNI_PYTHON, python3.14 ... python3.10, python3, or uv)
#   2. creates/reuses ~/.claude-mcp-servers/omni-ai-mcp/venv (OMNI_INSTALL_DIR to change)
#   3. installs this checkout in EDITABLE mode: a later `git pull` is the whole update
#   4. registers `omni-ai-mcp` in Claude Code (user scope, ~/.claude.json, mode 600)
#      with your API keys; the keys never appear on a command line
#
# Prefer `uvx omni-ai-mcp` or scripts/install_release.sh if you don't need a checkout.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
warn() { echo -e "  ${YELLOW}!${NC} $*"; }
die()  { echo -e "${RED}Error:${NC} $*" >&2; exit 1; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${OMNI_INSTALL_DIR:-$HOME/.claude-mcp-servers/omni-ai-mcp}"
VENV="$INSTALL_DIR/venv"
GEMINI_KEY="${1:-${GEMINI_API_KEY:-}}"
OPENROUTER_KEY="${2:-${OPENROUTER_API_KEY:-}}"

[ -f "$REPO_DIR/pyproject.toml" ] || die "run this script from an omni-ai-mcp checkout"
[ -n "$GEMINI_KEY" ] || die "usage: ./setup.sh GEMINI_API_KEY [OPENROUTER_API_KEY]  (get a key at https://aistudio.google.com/apikey)"
[[ "$GEMINI_KEY" == AIza* ]] || warn "the Gemini key does not start with 'AIza': double-check it"

echo "omni-ai-mcp setup (from source: $REPO_DIR)"

# --- 1. Python >= 3.10 --------------------------------------------------------
py_ok() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; }
PYTHON="${OMNI_PYTHON:-}"
if [ -z "$PYTHON" ]; then
  for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && py_ok "$candidate"; then PYTHON="$candidate"; break; fi
  done
fi
if [ -z "$PYTHON" ] && command -v uv >/dev/null 2>&1; then
  uv python install 3.12 >/dev/null 2>&1 || true
  PYTHON="$(uv python find '>=3.10' 2>/dev/null || true)"
fi
[ -n "$PYTHON" ] && py_ok "$PYTHON" || die "Python 3.10+ is required (install it, or install uv: https://docs.astral.sh/uv/)"
ok "Python $("$PYTHON" -c 'import platform; print(platform.python_version())') ($PYTHON)"

command -v claude >/dev/null 2>&1 && ok "Claude Code CLI" \
  || warn "Claude Code CLI not found: registering in ~/.claude.json anyway (https://docs.claude.com/en/docs/claude-code)"

# --- 2-3. venv + editable install --------------------------------------------
mkdir -p "$INSTALL_DIR"
[ -x "$VENV/bin/python3" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/python3" -m pip install --quiet --upgrade pip
"$VENV/bin/python3" -m pip install --quiet -e "$REPO_DIR"
"$VENV/bin/python3" -m pip check >/dev/null || die "dependency check failed (pip check)"
VERSION="$(cd / && "$VENV/bin/python3" -c 'import app; print(app.__version__)')"
TOOLS="$(cd / && GEMINI_API_KEY=x GEMINI_ACTIVITY_LOG=false "$VENV/bin/python3" -c 'from app.server import mcp; print(len(mcp._tool_manager._tools))' 2>/dev/null)"
ok "omni-ai-mcp $VERSION installed (editable) in $VENV, $TOOLS tools"

# --- 4. register in Claude Code ----------------------------------------------
# Written directly (not `claude mcp add -e KEY=...`): keys passed as command-line
# arguments are visible to every local user in the process list.
CLAUDE_JSON="$HOME/.claude.json"
if [ -f "$CLAUDE_JSON" ]; then
  BACKUP="$CLAUDE_JSON.bak-$(date +%Y%m%d-%H%M%S)-omni-setup"
  (umask 077 && cp "$CLAUDE_JSON" "$BACKUP")
  chmod 600 "$BACKUP"
fi
OMNI_GEMINI_KEY="$GEMINI_KEY" OMNI_OPENROUTER_KEY="$OPENROUTER_KEY" CLAUDE_JSON="$CLAUDE_JSON" VENV="$VENV" \
  "$VENV/bin/python3" - <<'PY'
import json, os
path, venv = os.environ["CLAUDE_JSON"], os.environ["VENV"]
data = json.load(open(path)) if os.path.exists(path) else {}
servers = data.setdefault("mcpServers", {})
env = dict(servers.get("omni-ai-mcp", {}).get("env", {}))
env["GEMINI_API_KEY"] = os.environ["OMNI_GEMINI_KEY"]
if os.environ.get("OMNI_OPENROUTER_KEY"):
    env["OPENROUTER_API_KEY"] = os.environ["OMNI_OPENROUTER_KEY"]
servers["omni-ai-mcp"] = {"type": "stdio", "command": f"{venv}/bin/python3", "args": ["-m", "app.server"], "env": env}
tmp = f"{path}.tmp-omni-{os.getpid()}"
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(data, f, indent=2)
os.replace(tmp, path)
os.chmod(path, 0o600)
PY
ok "registered in Claude Code (user scope, ~/.claude.json mode 600)${OPENROUTER_KEY:+, OpenRouter enabled}"

echo
echo "Done. Restart Claude Code, then check with:  claude mcp list"
echo "Update later with:  git -C \"$REPO_DIR\" pull   (editable install, no reinstall needed)"
