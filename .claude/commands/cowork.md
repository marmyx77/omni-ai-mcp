---
description: "Claude + Gemini co-working on the same task for two independent perspectives. Usage: /cowork <task or question>"
---

Invoke the cowork agent to work on: $ARGUMENTS

The cowork agent will:
1. Have Claude analyze the problem independently
2. Have Gemini analyze the same problem independently (via ask_gemini)
3. Compare the two perspectives — where they agree = high confidence, where they diverge = investigate
4. Synthesize a final recommendation combining the best of both

This is especially useful for:
- Validating architectural decisions before committing
- Getting a second opinion on complex code
- Stress-testing a solution against two independent critics
- Researching current information (Gemini) + applying it to code (Claude)
