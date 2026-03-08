---
description: "Setup omni-ai-mcp: enter your API key in chat to configure everything automatically"
---

Guide the user through setting up omni-ai-mcp by asking for their API key directly in chat, then configuring it automatically. Follow these steps in order:

**Step 1 — Check uv**
Run `which uvx` silently. If uvx is NOT installed, tell the user:
"First, install uv by running this in your terminal, then restart Claude Code:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Then run /setup again."
Stop here if uvx is missing.

**Step 2 — Ask for the Gemini API key**
Check if GEMINI_API_KEY is already set by running `echo $GEMINI_API_KEY`.

If NOT set, ask the user:
"Please paste your **Gemini API key** here. Get one free at https://aistudio.google.com/app/apikey"

Wait for the user to reply with the key, then use it in Step 3.
If it IS already set, use the existing value from the environment.

**Step 3 — Register the MCP server with the key**
Run this command with the key the user provided (replace KEY with the actual key):
```
claude mcp add omni-ai-mcp -e GEMINI_API_KEY=KEY -- uvx omni-ai-mcp
```
If the command fails because omni-ai-mcp already exists, run:
```
claude mcp remove omni-ai-mcp
claude mcp add omni-ai-mcp -e GEMINI_API_KEY=KEY -- uvx omni-ai-mcp
```

**Step 4 — Ask for OpenRouter key (optional)**
Ask: "Do you have an **OpenRouter API key**? (optional — enables 400+ models like GPT-4o, Llama, Mistral). Paste it here or type **skip**."

If they provide a key (not "skip"), run:
```
claude mcp remove omni-ai-mcp
claude mcp add omni-ai-mcp -e GEMINI_API_KEY=GEMINI_KEY -e OPENROUTER_API_KEY=OR_KEY -- uvx omni-ai-mcp
```

**Step 5 — Done**
Tell the user: "✅ Setup complete! **Restart Claude Code** to activate the tools. After restart, you'll have access to 20 AI tools: /gemini, /gemini-research, /gemini-review, /cowork and more."
