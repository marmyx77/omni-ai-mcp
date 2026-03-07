---
description: "Analyze a codebase or directory with Gemini's 1M context window. Usage: /gemini-analyze [path or files]"
---

Use the gemini_analyze_codebase tool to analyze: $ARGUMENTS

If no argument is provided, use the current working directory.

Choose analysis_type based on the argument:
- "security" or "vulnerabilities" in argument → analysis_type="security"
- "architecture" or "design" in argument → analysis_type="architecture"
- "refactor" or "clean" in argument → analysis_type="refactoring"
- "docs" or "documentation" in argument → analysis_type="documentation"
- default → analysis_type="architecture"

Return the full analysis with actionable recommendations.
