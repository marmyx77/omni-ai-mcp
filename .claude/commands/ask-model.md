---
description: "Ask any AI model (Gemini, GPT-4o, Llama, Mistral, Claude via OpenRouter). Usage: /ask-model [model] [prompt]. Examples: /ask-model gpt-4o explain quantum computing, /ask-model gemini what is RLHF"
---

Parse $ARGUMENTS to extract the model and prompt:
- If the first word matches a known model name or provider alias (gpt-4o, gemini, llama, mistral, claude, flash, pro, openai/, meta-, anthropic/), use it as the model
- The rest is the prompt
- If no model is specified, use model="pro" (the newest Gemini flagship, Gemini 4 Argon today)

Use the ask_model tool with the extracted model and prompt.

Model aliases:
- "gpt-4o" or "gpt4o" → model="openai/gpt-4o"
- "llama" or "llama3" → model="meta-llama/llama-3.3-70b-instruct"
- "mistral" → model="mistralai/mistral-large-2512"
- "claude" → model="anthropic/claude-sonnet-5.5"
- "grok" → model="x-ai/grok-4.7"
- "deepseek" → model="deepseek/deepseek-v4-pro"
- "gemma" → model="gemma-4-31b-it"
- "gemini", "argon" or "pro" → model="pro" (auto-resolved to the newest Gemini flagship)
- "flash" → model="flash"

Return the response with clear attribution showing which model answered.
