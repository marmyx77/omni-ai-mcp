---
description: Ask any AI model (Gemini, GPT-4o, Llama, Mistral, Claude via OpenRouter). Usage: /ask-model [model] [prompt]. Examples: /ask-model gpt-4o explain quantum computing, /ask-model gemini what is RLHF
---

Parse $ARGUMENTS to extract the model and prompt:
- If the first word matches a known model name or provider alias (gpt-4o, gemini, llama, mistral, claude, flash, pro, openai/, meta-, anthropic/), use it as the model
- The rest is the prompt
- If no model is specified, use model="pro" (Gemini Pro)

Use the ask_model tool with the extracted model and prompt.

Model aliases:
- "gpt-4o" or "gpt4o" → model="openai/gpt-4o"
- "llama" or "llama3" → model="meta-llama/llama-3.3-70b"
- "mistral" → model="mistral/mistral-large-latest"
- "claude" → model="anthropic/claude-3.5-sonnet"
- "gemini" or "pro" → model="pro" (auto-resolved to Gemini Pro)
- "flash" → model="flash"

Return the response with clear attribution showing which model answered.
