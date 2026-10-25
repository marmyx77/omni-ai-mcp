"""
Brainstorm Tool

Advanced brainstorming with multiple methodologies.
"""

from typing import Optional

from ...tools.registry import tool
from ...utils.file_refs import expand_file_references
from ...utils.tokens import check_prompt_size
from .ask_gemini import ask_gemini


def get_methodology_instructions(methodology: str, domain: str = None) -> str:
    """Get methodology-specific instructions for structured brainstorming."""
    methodologies = {
        "divergent": """**Divergent Thinking Approach:**
- Generate maximum quantity of ideas without self-censoring
- Build on wild or seemingly impractical ideas
- Combine unrelated concepts for unexpected solutions
- Use "Yes, and..." thinking to expand each concept
- Postpone evaluation until all ideas are generated""",

        "convergent": """**Convergent Thinking Approach:**
- Focus on refining and improving existing concepts
- Synthesize related ideas into stronger solutions
- Apply critical evaluation criteria
- Prioritize based on feasibility and impact
- Develop implementation pathways for top ideas""",

        "scamper": """**SCAMPER Creative Triggers:**
- **Substitute:** What can be substituted or replaced?
- **Combine:** What can be combined or merged?
- **Adapt:** What can be adapted from other domains?
- **Modify:** What can be magnified, minimized, or altered?
- **Put to other use:** How else can this be used?
- **Eliminate:** What can be removed or simplified?
- **Reverse:** What can be rearranged or reversed?""",

        "design-thinking": """**Human-Centered Design Thinking:**
- **Empathize:** Consider user needs, pain points, and contexts
- **Define:** Frame problems from user perspective
- **Ideate:** Generate user-focused solutions
- **Consider Journey:** Think through complete user experience
- **Prototype Mindset:** Focus on testable, iterative concepts""",

        "lateral": """**Lateral Thinking Approach:**
- Make unexpected connections between unrelated fields
- Challenge fundamental assumptions
- Use random word association to trigger new directions
- Apply metaphors and analogies from other domains
- Reverse conventional thinking patterns""",

        "auto": f"""**AI-Optimized Approach:**
{f'Given the {domain} domain, I will apply the most effective combination of:' if domain else 'I will intelligently combine multiple methodologies:'}
- Divergent exploration with domain-specific knowledge
- SCAMPER triggers and lateral thinking
- Human-centered perspective for practical value"""
    }
    return methodologies.get(methodology, methodologies["auto"])


BRAINSTORM_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "Topic or challenge to brainstorm"},
        "context": {"type": "string", "description": "Additional context or background", "default": ""},
        "methodology": {
            "type": "string",
            "enum": ["auto", "divergent", "convergent", "scamper", "design-thinking", "lateral"],
            "description": "Brainstorming framework: auto (AI selects), divergent (many ideas), convergent (refine), scamper (creative triggers), design-thinking (human-centered), lateral (unexpected connections)",
            "default": "auto"
        },
        "domain": {
            "type": "string",
            "description": "Domain context: software, business, creative, marketing, product, research, etc."
        },
        "constraints": {
            "type": "string",
            "description": "Known limitations: budget, time, technical, legal, etc."
        },
        "idea_count": {
            "type": "integer",
            "description": "Target number of ideas to generate",
            "default": 10
        },
        "include_analysis": {
            "type": "boolean",
            "description": "Include feasibility, impact, and innovation scores for each idea",
            "default": True
        }
    },
    "required": ["topic"]
}


@tool(
    name="gemini_brainstorm",
    description="Advanced brainstorming with multiple methodologies. Uses the newest Gemini flagship for creative reasoning with structured frameworks like SCAMPER, Design Thinking, and more.",
    input_schema=BRAINSTORM_SCHEMA,
    tags=["text", "creative"]
)
def brainstorm(
    topic: str,
    context: str = "",
    methodology: str = "auto",
    domain: Optional[str] = None,
    constraints: Optional[str] = None,
    idea_count: int = 10,
    include_analysis: bool = True
) -> str:
    """
    Advanced brainstorming with multiple methodologies.

    Methodologies:
    - auto: AI selects best approach
    - divergent: Generate many ideas without filtering
    - convergent: Refine and improve existing concepts
    - scamper: Systematic creative triggers
    - design-thinking: Human-centered approach
    - lateral: Unexpected connections and assumption challenges

    Supports @file references in topic and context to include file contents.
    """
    # Expand @file references in topic and context
    topic = expand_file_references(topic)
    if context:
        context = expand_file_references(context)

    # Check combined prompt size after file expansion
    combined = topic + (context or "")
    size_error = check_prompt_size(combined)
    if size_error:
        return f"**Error**: {size_error['message']}"

    framework = get_methodology_instructions(methodology, domain)

    prompt = f"""# BRAINSTORMING SESSION

## Core Challenge
{topic}

## Methodology Framework
{framework}

## Context Engineering
*Use the following context to inform your reasoning:*
{f'**Domain Focus:** {domain} - Apply domain-specific knowledge, terminology, and best practices.' if domain else ''}
{f'**Constraints & Boundaries:** {constraints}' if constraints else ''}
{f'**Background Context:** {context}' if context else ''}

## Output Requirements
- Generate {idea_count} distinct, creative ideas
- Each idea should be unique and non-obvious
- Focus on actionable, implementable concepts
- Use clear, descriptive naming
- Provide brief explanations for each idea
"""

    if include_analysis:
        prompt += """
## Analysis Framework
For each idea, provide:
- **Feasibility:** Implementation difficulty (1-5 scale)
- **Impact:** Potential value/benefit (1-5 scale)
- **Innovation:** Uniqueness/creativity (1-5 scale)
- **Quick Assessment:** One-sentence evaluation
"""

    prompt += """
## Format
Present ideas in a structured format:

### Idea [N]: [Creative Name]
**Description:** [2-3 sentence explanation]
"""

    if include_analysis:
        prompt += """**Feasibility:** [1-5] | **Impact:** [1-5] | **Innovation:** [1-5]
**Assessment:** [Brief evaluation]
"""

    prompt += """
---

**Before finalizing, review the list: remove near-duplicates and ensure each idea satisfies the constraints.**

Begin brainstorming session:"""

    return ask_gemini(prompt, model="pro", temperature=0.7)
