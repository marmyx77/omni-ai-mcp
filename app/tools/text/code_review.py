"""
Code Review Tool

Code analysis with specific focus areas.
"""

from typing import Optional

from ...tools.registry import tool
from ...utils.file_refs import expand_file_references
from ...utils.tokens import check_prompt_size
from .ask_gemini import ask_gemini


CODE_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "Code to review"},
        "focus": {
            "type": "string",
            "description": "Focus area: security, performance, readability, bugs, general",
            "default": "general"
        },
        "model": {
            "type": "string",
            "enum": ["pro", "flash"],
            "description": "pro (default): newest Gemini flagship - thorough analysis. flash: faster but less detailed",
            "default": "pro"
        }
    },
    "required": ["code"]
}


@tool(
    name="gemini_code_review",
    description="Have Gemini review code with specific focus. Uses the newest Gemini flagship for best reasoning.",
    input_schema=CODE_REVIEW_SCHEMA,
    tags=["text", "code"]
)
def code_review(code: str, focus: str = "general", model: str = "pro") -> str:
    """
    Code review with specific focus.

    Supports @file references in code parameter to include file contents:
    - @src/main.py - Review a specific file
    - @*.py - Review multiple files matching pattern
    """
    # Expand @file references in code
    code = expand_file_references(code)

    # Check prompt size after file expansion
    size_error = check_prompt_size(code)
    if size_error:
        return f"**Error**: {size_error['message']}"

    prompt = f"""Review this code with focus on {focus}:

```
{code}
```

Provide specific, actionable feedback on:
1. Potential issues or bugs
2. Security concerns
3. Performance optimizations
4. Best practices
5. Code clarity"""

    return ask_gemini(prompt, model=model, temperature=0.2)
