"""
Challenge Tool

Critical thinking tool - challenges ideas, plans, or code to find flaws.
"""

from typing import Optional

from ...tools.registry import tool
from ...utils.file_refs import expand_file_references
from ...utils.tokens import check_prompt_size
from .ask_gemini import ask_gemini


FOCUS_INSTRUCTIONS = {
    "security": """**Security Focus:**
- Identify potential vulnerabilities (OWASP Top 10)
- Find authentication/authorization gaps
- Look for injection risks (SQL, command, XSS)
- Check for data exposure risks
- Evaluate cryptographic weaknesses""",

    "performance": """**Performance Focus:**
- Identify bottlenecks and inefficiencies
- Find N+1 query problems or expensive operations
- Look for memory leaks or resource issues
- Check for scalability concerns
- Evaluate caching opportunities missed""",

    "maintainability": """**Maintainability Focus:**
- Find overly complex or unclear code/design
- Identify tight coupling and poor abstractions
- Look for violation of SOLID principles
- Check for testing difficulties
- Evaluate documentation gaps""",

    "scalability": """**Scalability Focus:**
- Identify single points of failure
- Find state management issues
- Look for horizontal scaling blockers
- Check for database/storage bottlenecks
- Evaluate load distribution concerns""",

    "cost": """**Cost Focus:**
- Identify expensive operations or resources
- Find inefficient resource utilization
- Look for hidden costs (API calls, storage, compute)
- Check for cost scaling concerns
- Evaluate cheaper alternatives""",

    "general": """**General Critical Analysis:**
- Find logical flaws and inconsistencies
- Identify hidden assumptions
- Look for edge cases and failure modes
- Check for missing requirements
- Evaluate alternative approaches"""
}


CHALLENGE_SCHEMA = {
    "type": "object",
    "properties": {
        "statement": {
            "type": "string",
            "description": "The idea, plan, architecture, or code to critique. Be specific about what you want challenged."
        },
        "context": {
            "type": "string",
            "description": "Optional background context, constraints, or requirements that should be considered.",
            "default": ""
        },
        "focus": {
            "type": "string",
            "enum": ["general", "security", "performance", "maintainability", "scalability", "cost"],
            "description": "Specific area to focus the critique on",
            "default": "general"
        }
    },
    "required": ["statement"]
}


@tool(
    name="gemini_challenge",
    description="Critical thinking tool - challenges ideas, plans, or code to find flaws, risks, and better alternatives. Use this before implementing to catch issues early. Does NOT agree with the user - actively looks for problems.",
    input_schema=CHALLENGE_SCHEMA,
    tags=["text", "critical"]
)
def challenge(
    statement: str,
    context: str = "",
    focus: str = "general"
) -> str:
    """
    Critical thinking tool - challenges ideas, plans, or code to find flaws.

    Acts as a "Devil's Advocate" to:
    - Find potential problems before implementation
    - Identify risks and edge cases
    - Suggest better alternatives
    - Challenge assumptions

    Does NOT agree with the user - actively looks for problems.
    """
    # Expand @file references
    statement = expand_file_references(statement)
    if context:
        context = expand_file_references(context)

    # Check prompt size
    combined = statement + (context or "")
    size_error = check_prompt_size(combined)
    if size_error:
        return f"**Error**: {size_error['message']}"

    focus_instruction = FOCUS_INSTRUCTIONS.get(focus, FOCUS_INSTRUCTIONS["general"])
    context_section = "## Additional Context\n" + context if context else ""

    prompt = f"""# CRITICAL ANALYSIS REQUEST

## Your Role
You are a critical thinker and "Devil's Advocate". Your job is to find problems, risks, and flaws.

**IMPORTANT INSTRUCTIONS:**
- Do NOT agree with or validate the idea
- Do NOT be encouraging or positive
- Do NOT soften your critique
- Be direct, honest, and thorough
- Find REAL problems, not hypothetical nitpicks
- Prioritize by severity

{focus_instruction}

## Statement to Challenge
{statement}

{context_section}

## Required Output Structure

### 1. Critical Flaws (Must Fix)
List the most serious problems that would cause failure if not addressed.

### 2. Significant Risks
Problems that may not be immediately fatal but pose real danger.

### 3. Questionable Assumptions
Assumptions made that may not hold true.

### 4. Missing Considerations
Important aspects not addressed in the proposal.

### 5. Better Alternatives
Different approaches that might work better, with brief rationale.

### 6. Devil's Advocate Summary
A 2-3 sentence harsh but fair summary of why this might fail.

---
Be thorough but actionable. Focus on the most impactful issues first.
"""

    return ask_gemini(prompt, model="pro", temperature=0.4)
