"""
omni-ai-mcp v4.0.0
Multi-AI MCP bridge: Gemini + OpenRouter.

Features:
- FastMCP SDK for protocol compliance
- 20 tools: Gemini suite + gemini_list_models + ask_model (multi-provider)
- Dynamic model registry: auto-discovers available models via API
- OpenRouter integration: 400+ models (optional, OPENROUTER_API_KEY)
- Dual conversation storage: local (SQLite) or cloud (Interactions API)
- Security: sandboxing, secrets sanitization, cross-platform file locking
"""

__version__ = "4.0.0"

from .server import main

__all__ = ["__version__", "main"]
