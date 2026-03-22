---
description: "Ask Gemini Pro anything with full context. Usage: /gemini <question or task>"
---

Use the `ask_gemini` MCP tool to answer the following request.

## Context is everything

Gemini only knows what you explicitly give it. It has no access to your session, filesystem, or conversation history unless you pass it in.

**Before calling `ask_gemini`, always include in the prompt:**
- The relevant files (use @file syntax or paste content inline)
- The full error message or output, if debugging
- What you already tried, if iterating
- Any related config, types, or dependencies that affect the answer

The more complete the context, the more precise and actionable the answer.

## Model selection

- `model="pro"` — complex reasoning, architecture review, deep analysis, nuanced questions
- `model="flash"` — quick answers, simple lookups, fast iteration

## Web search

Add `thinking_level="high"` for questions that benefit from multi-step reasoning.
For questions about current events, recent library versions, or real-world data, `ask_gemini` automatically uses Google Search grounding.

## The request

$ARGUMENTS
