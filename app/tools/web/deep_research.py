"""
Deep Research Tool

Execute comprehensive research tasks using Google's Deep Research Agent.
Uses the Interactions API for autonomous multi-step research with citations.
"""

import time
from typing import Optional

from ...tools.registry import tool
from ...services import client, is_available, get_error
from ...services.model_registry import model_registry
from ...core import config, log_progress
from ... import __version__


def extract_interaction_text(interaction) -> str:
    """Extract output text from an interaction across SDK schemas.

    Handles the new 'steps' schema (google-genai >= 2.0, Interactions API revision
    2026-05-20) via the `output_text` convenience property and the `steps` array,
    and falls back to the legacy `outputs`/`response` shapes for older SDKs.
    """
    # New 'steps' schema: concatenate the text of ALL model output steps.
    # Do NOT trust `output_text` first: on multi-step interactions (deep research)
    # it only carries the LAST chunk (observed 2026-07-05: a 48k-char report
    # truncated to its final 23k). Steps' content is a list of typed items
    # (TextContent/ImageContent): collect only the .text ones, in order.
    steps = getattr(interaction, "steps", None)
    if steps:
        parts = []
        for step in steps:
            stype = getattr(step, "type", None)
            if stype not in ("model_output", "agent_output", "output", "text"):
                continue
            content = getattr(step, "content", None) or getattr(step, "text", None)
            if isinstance(content, str):
                parts.append(content)
                continue
            for item in (content or []):
                item_text = getattr(item, "text", None)
                if item_text:
                    parts.append(item_text)
        if parts:
            return "".join(parts)

    # SDK 2.x convenience property (fallback: last output chunk only)
    text = getattr(interaction, "output_text", None)
    if text:
        return text

    # Legacy fallbacks
    outputs = getattr(interaction, "outputs", None)
    if outputs:
        last = outputs[-1]
        return getattr(last, "text", None) or str(last)
    resp = getattr(interaction, "response", None)
    if resp is not None:
        return getattr(resp, "text", None) or str(resp)
    return str(interaction)


# Static fallback only. The agent used at call time comes from the registry
# (category "deep_research": newest deep-research-preview-MM-YYYY the API
# exposes, or the GEMINI_MODEL_DEEP_RESEARCH override). Freezing it at import
# is what kept dead agent IDs alive for months (4.0.0 → 4.4.0).
DEEP_RESEARCH_AGENT = config.model_deep_research


def resolve_agent() -> str:
    """Deep Research agent ID for this call (env override > auto-detect > fallback)."""
    return model_registry.resolve("deep_research")


def format_deep_research_error(exc: Exception, agent: str, interaction_id: Optional[str] = None) -> str:
    """
    Turn an API exception into a message that says WHAT failed and WHICH code answered.

    The old message ("Deep Research Agent not available") hid the real error and
    the agent ID, so a stale install kept reporting the same line for months.
    """
    error_msg = str(exc)
    lower = error_msg.lower()
    footer = (
        f"\n\nAgent: `{agent}` · omni-ai-mcp {__version__}\n"
        f"Run `gemini_list_models` to see the agent the registry resolves and where it comes from."
    )
    if interaction_id and ("not found" in lower or "404" in lower):
        return (
            f"Error: interaction `{interaction_id}` not found (expired or wrong continuation_id).\n"
            f"API said: {error_msg}" + footer
        )
    if "not found" in lower or "404" in lower:
        return (
            f"Error: the Deep Research agent `{agent}` was not found by the API.\n"
            f"It was probably renamed or retired upstream; the registry auto-detects the newest "
            f"`deep-research-preview-MM-YYYY` on the next refresh (1 h), or set GEMINI_MODEL_DEEP_RESEARCH.\n"
            f"API said: {error_msg}" + footer
        )
    if "quota" in lower or "rate" in lower or "resource_exhausted" in lower:
        return (
            f"Error: API quota exceeded. Deep Research uses significant compute; try again later.\n"
            f"API said: {error_msg}" + footer
        )
    if "permission" in lower or "403" in lower:
        return (
            f"Error: the API key is not allowed to use the Deep Research agent.\n"
            f"API said: {error_msg}" + footer
        )
    return f"Error: {error_msg}" + footer

# Polling configuration
POLL_INTERVAL_SECONDS = 15  # Check every 15 seconds
MAX_POLL_TIME_SECONDS = 3600  # Max 1 hour (research can take 5-60 minutes)


DEEP_RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Research topic or question. Be specific - the agent will conduct comprehensive web research."
        },
        "max_wait_minutes": {
            "type": "integer",
            "description": "Maximum time to wait for research completion (5-60 minutes). Default: 30",
            "default": 30,
            "minimum": 5,
            "maximum": 60
        },
        "continuation_id": {
            "type": "string",
            "description": "Optional interaction ID to continue a previous research session"
        }
    },
    "required": ["query"]
}


@tool(
    name="gemini_deep_research",
    description="""Execute comprehensive research using Google's Deep Research Agent.

The agent autonomously:
- Conducts multi-step web searches
- Synthesizes findings into a detailed report
- Provides citations and sources

Use for:
- Market research and competitive analysis
- Technical deep dives
- Literature reviews
- Trend analysis
- Any topic requiring thorough investigation

Note: Research typically takes 5-30 minutes depending on complexity.
The tool will poll for completion and return the full report.""",
    input_schema=DEEP_RESEARCH_SCHEMA,
    tags=["web", "research", "agent"]
)
def deep_research(
    query: str,
    max_wait_minutes: int = 30,
    continuation_id: Optional[str] = None
) -> str:
    """
    Execute deep research using Google's Interactions API.

    Args:
        query: Research topic or question
        max_wait_minutes: Maximum wait time (5-60 minutes)
        continuation_id: Optional ID to continue previous research

    Returns:
        Comprehensive research report with citations
    """
    if not is_available():
        return f"Error: {get_error()}"

    max_wait_seconds = max_wait_minutes * 60
    agent = resolve_agent()

    try:
        log_progress(f"deep_research: Starting research on '{query[:50]}...' (agent={agent}, v{__version__})")

        # Create interaction with deep research agent
        create_kwargs = {
            "input": query,
            "agent": agent,
            "background": True  # Required for agents
        }

        # Continue from previous interaction if provided
        if continuation_id:
            create_kwargs["previous_interaction_id"] = continuation_id
            log_progress(f"deep_research: Continuing from interaction {continuation_id}")

        # Start the research
        interaction = client.interactions.create(**create_kwargs)
        interaction_id = interaction.id

        log_progress(f"deep_research: Interaction started (ID: {interaction_id})")

        # Poll for completion
        start_time = time.time()
        last_status = None

        while True:
            elapsed = time.time() - start_time

            # Check timeout
            if elapsed > max_wait_seconds:
                return (
                    f"Research timed out after {max_wait_minutes} minutes.\n\n"
                    f"The research is still running in the background.\n"
                    f"Use continuation_id='{interaction_id}' to check status later."
                )

            # Get current status
            interaction = client.interactions.get(interaction_id)
            status = getattr(interaction, 'status', 'unknown')

            # Log status changes
            if status != last_status:
                elapsed_mins = int(elapsed / 60)
                log_progress(f"deep_research: Status={status} ({elapsed_mins}m elapsed)")
                last_status = status

            # Check for completion
            if status == "completed":
                log_progress(f"deep_research: Completed in {int(elapsed)}s")
                break
            elif status in ["failed", "cancelled"]:
                error_msg = getattr(interaction, 'error', 'Unknown error')
                return f"Research {status}: {error_msg}"

            # Wait before next poll
            time.sleep(POLL_INTERVAL_SECONDS)

        # Extract the research report (handles new 'steps' schema + legacy)
        report = extract_interaction_text(interaction)
        if report and report != str(interaction):
            elapsed_mins = round((time.time() - start_time) / 60, 1)
            result = f"# Deep Research Report\n\n"
            result += f"**Query:** {query}\n"
            result += f"**Duration:** {elapsed_mins} minutes\n\n"
            result += "---\n\n"
            result += report
            result += f"\n\n---\n*interaction_id: {interaction_id}*"
            return result
        else:
            return f"Research completed but no output found. ID: {interaction_id}"

    except AttributeError as e:
        # Handle case where Interactions API is not available in SDK version
        if "interactions" in str(e):
            return (
                "Error: Interactions API not available.\n"
                "The google-genai SDK version may not support the Interactions API yet.\n"
                "Required: google-genai >= 2.0.0"
            )
        raise
    except Exception as e:
        return format_deep_research_error(e, agent, continuation_id)
