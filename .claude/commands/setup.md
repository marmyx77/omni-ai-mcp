---
description: "Setup omni-ai-mcp: check API keys, uv install, and configure your environment"
---

Run the following checks and guide the user to complete setup of omni-ai-mcp.

**Step 1 — Check uv/uvx**
Run `which uvx` to see if uvx is installed. If not installed, tell the user to run:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Then restart their terminal.

**Step 2 — Check GEMINI_API_KEY**
Run `echo $GEMINI_API_KEY` to check if the key is set.

- If it IS set: confirm it's configured and show the first 8 characters followed by `...` for verification.
- If it is NOT set: tell the user to add this line to their shell profile (`~/.zshrc` or `~/.bashrc`):
  ```
  export GEMINI_API_KEY=your_key_here
  ```
  And to get a key at: https://aistudio.google.com/app/apikey
  Then run: `source ~/.zshrc` (or `source ~/.bashrc`)

**Step 3 — Check OPENROUTER_API_KEY (optional)**
Run `echo $OPENROUTER_API_KEY`. Tell the user:
- If set: OpenRouter is configured, 400+ models available.
- If not set: OpenRouter is optional (enables GPT-4o, Llama, Mistral, etc.). To enable it later, get a key at https://openrouter.ai/keys and add `export OPENROUTER_API_KEY=your_key_here` to their shell profile.

**Step 4 — Verify MCP server**
Run `claude mcp list` to check if `omni-ai-mcp` appears in the list.
- If it appears: setup is complete! Tell the user to restart Claude Code to apply any env changes.
- If it does NOT appear: the plugin may not have been installed yet. Tell the user to install `omni-ai-mcp-plugin-vX.Y.Z.zip` from https://github.com/marmyx77/omni-ai-mcp/releases using `/install-plugin <path-to-zip>`.

**Summary**
At the end, print a clear ✅ / ❌ checklist for: uv installed, GEMINI_API_KEY set, OPENROUTER_API_KEY set (optional), MCP server registered.
