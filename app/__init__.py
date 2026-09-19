"""
omni-ai-mcp v4.4.1
Multi-AI MCP bridge: Gemini + OpenRouter.

Features:
- FastMCP SDK for protocol compliance
- 21 tools: Gemini suite + gemini_list_models + ask_model (multi-provider) + gemini_transcribe_audio
- Dynamic model registry: auto-discovers available models via API
- OpenRouter integration: 400+ models (optional, OPENROUTER_API_KEY)
- Dual conversation storage: local (SQLite) or cloud (Interactions API)
- Security: sandboxing, secrets sanitization, cross-platform file locking
"""

__version__ = "4.7.0"

from .server import main

__all__ = ["__version__", "main"]
