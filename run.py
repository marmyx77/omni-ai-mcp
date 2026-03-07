#!/usr/bin/env python3
"""
omni-ai-mcp v3.0.0
Production MCP server for Google Gemini AI.

Usage:
    python run.py
    # or
    python -m app.server

Requirements:
    - Python 3.9+
    - GEMINI_API_KEY environment variable
    - mcp[cli] package (pip install 'mcp[cli]')
"""

import sys
import os

# Ensure Python 3.9+
if sys.version_info < (3, 9):
    print("Error: Python 3.9 or higher is required", file=sys.stderr)
    print(f"Current version: {sys.version}", file=sys.stderr)
    sys.exit(1)

# Check for API key
if not os.environ.get("GEMINI_API_KEY"):
    print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
    print("Get your API key from: https://aistudio.google.com/apikey", file=sys.stderr)
    sys.exit(1)

# Add the server directory to path so 'app' can be imported
server_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, server_dir)

from app import main

if __name__ == "__main__":
    main()
