---
description: Devil's Advocate - challenge an idea, plan, or code to find flaws. Usage: /gemini-challenge <statement>
---

Use the gemini_challenge tool to critically analyze the following: $ARGUMENTS

If $ARGUMENTS contains a file path (e.g. @src/main.py), include the file content.
Set focus="general" unless the argument implies a specific area:
- mentions "security" or "auth" → focus="security"
- mentions "performance" or "slow" → focus="performance"
- mentions "scale" or "users" → focus="scalability"
- mentions "cost" or "price" → focus="cost"
- mentions "maintain" or "refactor" → focus="maintainability"

Present the critique directly. Do not soften the findings.
