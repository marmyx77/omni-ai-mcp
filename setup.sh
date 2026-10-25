#!/usr/bin/env bash
# Install omni-ai-mcp from this source checkout and register it in Claude Code.
#
#   ./setup.sh GEMINI_API_KEY [OPENROUTER_API_KEY]
#   GEMINI_API_KEY=... ./setup.sh
#
# What it does:
#   1. picks a Python >= 3.10 (OMNI_PYTHON, python3.14 ... python3.10, python3, or uv)
#   2. creates/reuses ~/.claude-mcp-servers/omni-ai-mcp/venv (OMNI_INSTALL_DIR to change)
#   3. installs this checkout in EDITABLE mode: a later `git pull` is the whole update
#   4. registers `omni-ai-mcp` in Claude Code (user scope) with your API keys
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

command -v claude >/dev/null 2>&1 || die "Claude Code CLI not found (https://docs.claude.com/en/docs/claude-code)"
ok "Claude Code CLI"

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
claude mcp remove omni-ai-mcp -s user >/dev/null 2>&1 || true
ENV_ARGS=(-e "GEMINI_API_KEY=$GEMINI_KEY")
[ -n "$OPENROUTER_KEY" ] && ENV_ARGS+=(-e "OPENROUTER_API_KEY=$OPENROUTER_KEY")
claude mcp add omni-ai-mcp --scope user "${ENV_ARGS[@]}" -- "$VENV/bin/python3" -m app.server >/dev/null
ok "registered in Claude Code (user scope)${OPENROUTER_KEY:+, OpenRouter enabled}"

echo
echo "Done. Restart Claude Code, then check with:  claude mcp list"
echo "Update later with:  git -C \"$REPO_DIR\" pull   (editable install, no reinstall needed)"
