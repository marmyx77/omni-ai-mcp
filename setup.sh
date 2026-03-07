#!/bin/bash
# omni-ai-mcp Setup Script v4.0.0
# Installs and configures the omni-ai-mcp server for Claude Code

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  omni-ai-mcp Setup v4.0.0               ║${NC}"
echo -e "${BLUE}║  Gemini + OpenRouter — 20 AI Tools         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# Check if API key was provided
API_KEY="$1"
OPENROUTER_KEY="${2:-}"  # Optional second argument

if [ -z "$API_KEY" ]; then
    echo -e "${RED}Error: Please provide your Gemini API key${NC}"
    echo ""
    echo "Usage: ./setup.sh YOUR_GEMINI_API_KEY [OPENROUTER_API_KEY]"
    echo ""
    echo "  Gemini key (required): https://aistudio.google.com/apikey"
    echo "  OpenRouter key (optional, for 400+ models): https://openrouter.ai"
    exit 1
fi

# Validate API key format (basic check)
if [[ ! "$API_KEY" =~ ^AIza ]]; then
    echo -e "${YELLOW}Warning: API key doesn't match expected format (AIza...)${NC}"
    echo "Continuing anyway..."
    echo ""
fi

# Check Python version (3.9+ required for is_relative_to and FastMCP)
echo "Checking requirements..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    echo "Install Python 3.9+ from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo -e "${RED}Error: Python 3.9+ required, found $PYTHON_VERSION${NC}"
    echo "Please upgrade Python: https://www.python.org/downloads/"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION"

# Check Claude Code CLI
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Error: Claude Code CLI not found${NC}"
    echo "Install with: npm install -g @anthropic-ai/claude-code"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Claude Code CLI"

# Create MCP server directory
INSTALL_DIR="$HOME/.claude-mcp-servers/omni-ai-mcp"
echo ""
echo "Installing server..."
mkdir -p "$INSTALL_DIR"

# Copy modular app package and entry point
cp -r app "$INSTALL_DIR/"
cp run.py "$INSTALL_DIR/"
cp pyproject.toml "$INSTALL_DIR/"
echo -e "  ${GREEN}✓${NC} Server installed to $INSTALL_DIR"

# Install Python dependencies
echo ""
echo "Installing dependencies..."

# Try different pip installation methods
install_deps() {
    pip3 install --quiet --user 'mcp[cli]>=1.0.0' 'google-genai>=1.55.0' 'pydantic>=2.0.0' 'defusedxml>=0.7.1' 'filelock>=3.0.0' 2>/dev/null || \
    pip3 install --quiet --break-system-packages 'mcp[cli]>=1.0.0' 'google-genai>=1.55.0' 'pydantic>=2.0.0' 'defusedxml>=0.7.1' 'filelock>=3.0.0' 2>/dev/null || \
    pip3 install --quiet 'mcp[cli]>=1.0.0' 'google-genai>=1.55.0' 'pydantic>=2.0.0' 'defusedxml>=0.7.1' 'filelock>=3.0.0'
}

if install_deps; then
    echo -e "  ${GREEN}✓${NC} Dependencies installed:"
    echo "      - mcp[cli] (FastMCP SDK)"
    echo "      - google-genai (Gemini SDK)"
    echo "      - pydantic (validation)"
else
    echo -e "${RED}Error: Failed to install dependencies${NC}"
    echo "Try manually: pip install 'mcp[cli]' google-genai pydantic"
    exit 1
fi

# Remove any existing MCP configuration
echo ""
echo "Configuring Claude Code..."
claude mcp remove omni-ai-mcp 2>/dev/null || true

# Add MCP server with environment variables
if [ -n "$OPENROUTER_KEY" ]; then
    claude mcp add omni-ai-mcp --scope user \
        -e GEMINI_API_KEY="$API_KEY" \
        -e OPENROUTER_API_KEY="$OPENROUTER_KEY" \
        -- python3 "$INSTALL_DIR/run.py"
    echo -e "  ${GREEN}✓${NC} OpenRouter integration enabled (400+ models)"
else
    claude mcp add omni-ai-mcp --scope user \
        -e GEMINI_API_KEY="$API_KEY" \
        -- python3 "$INSTALL_DIR/run.py"
fi

echo -e "  ${GREEN}✓${NC} MCP server registered"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Setup Complete!                           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Restart Claude Code (exit and reopen)"
echo "  2. Verify with: claude mcp list"
echo ""
echo "Available tools (20 MCP tools via FastMCP SDK):"
echo ""
echo "  ${BLUE}Multi-Provider${NC} (NEW in v4.0.0)"
echo "    • ask_model                - Gemini + 400+ models via OpenRouter"
echo "    • gemini_list_models       - Discover available models"
echo ""
echo "  ${BLUE}Text & Reasoning${NC}"
echo "    • ask_gemini               - Text generation with thinking"
echo "    • gemini_code_review       - Code analysis"
echo "    • gemini_brainstorm        - 6 methodologies"
echo "    • gemini_challenge         - Devil's advocate critique"
echo ""
echo "  ${BLUE}Research${NC}"
echo "    • gemini_web_search        - Web search with citations"
echo "    • gemini_deep_research     - Autonomous 5-60 min research"
echo ""
echo "  ${BLUE}Analysis${NC} (Gemini's 1M+ context advantage)"
echo "    • gemini_analyze_codebase  - Large codebase analysis"
echo "    • gemini_analyze_image     - Vision / OCR"
echo "    • gemini_generate_code     - Structured code generation"
echo "    • gemini_code_review       - Security & performance review"
echo ""
echo "  ${BLUE}Generation${NC} (Unique Gemini capabilities)"
echo "    • gemini_generate_image    - Imagen (up to 4K)"
echo "    • gemini_generate_video    - Veo 3.1 with native audio"
echo "    • gemini_text_to_speech    - 30 voices, multi-speaker"
echo ""
echo "  ${BLUE}RAG & Memory${NC}"
echo "    • gemini_file_search       - RAG document queries"
echo "    • gemini_create_file_store - Create RAG stores"
echo "    • gemini_upload_file       - Upload to RAG"
echo "    • gemini_list_file_stores  - List RAG stores"
echo "    • gemini_list_conversations- View conversation history"
echo ""
echo "Documentation: https://github.com/marcoarmellino/omni-ai-mcp"
echo ""
