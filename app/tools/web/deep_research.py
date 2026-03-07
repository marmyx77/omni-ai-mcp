"""
Deep Research Tool

Execute comprehensive research tasks using Google's Deep Research Agent.
Uses the Interactions API for autonomous multi-step research with citations.
"""

import time
from typing import Optional

from ...tools.registry import tool
from ...services import client, is_available, get_error
from ...core import config, log_progress


# Deep Research agent configuration (from config, overridable via GEMINI_MODEL_DEEP_RESEARCH)
DEEP_RESEARCH_AGENT = config.model_deep_research

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

    try:
        log_progress(f"deep_research: Starting research on '{query[:50]}...'")

        # Create interaction with deep research agent
        create_kwargs = {
            "input": query,
            "agent": DEEP_RESEARCH_AGENT,
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

        # Extract the research report
        if hasattr(interaction, 'outputs') and interaction.outputs:
            # Get the last output (final report)
            final_output = interaction.outputs[-1]

            # Extract text content
            if hasattr(final_output, 'text'):
                report = final_output.text
            else:
                report = str(final_output)

            # Add metadata
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
                "Required: google-genai >= 1.55.0"
            )
        raise
    except Exception as e:
        error_msg = str(e)

        # Handle common errors
        if "not found" in error_msg.lower():
            return (
                f"Error: Deep Research Agent not available.\n"
                f"Agent ID: {DEEP_RESEARCH_AGENT}\n"
                f"The agent may not be enabled for your API key or region."
            )
        elif "quota" in error_msg.lower() or "rate" in error_msg.lower():
            return (
                f"Error: API quota exceeded.\n"
                f"Deep Research uses significant compute resources.\n"
                f"Try again later or check your API quota limits."
            )

        return f"Error: {error_msg}"
