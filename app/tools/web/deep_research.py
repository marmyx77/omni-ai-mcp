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
TERMINAL_FAILURES = ("failed", "cancelled")


DEEP_RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Research topic or question. Be specific - the agent will conduct comprehensive web research. Leave EMPTY together with continuation_id to retrieve/resume a previous research (e.g. after a timeout)."
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
            "description": "Interaction ID of a previous research. With an empty query: retrieve its report (waiting if still running). With a query: start a follow-up research chained to it."
        }
    },
    "required": []
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
    query: str = "",
    max_wait_minutes: int = 30,
    continuation_id: Optional[str] = None
) -> str:
    """
    Execute deep research using Google's Interactions API.

    Three modes:
    - query only: start a new research and wait for it (up to max_wait_minutes)
    - continuation_id only: retrieve that research's report, waiting if it is still running
      (this is how a timed-out research is picked up later)
    - both: start a follow-up research chained to a COMPLETED previous one

    Returns:
        Comprehensive research report with citations, or an actionable message
    """
    if not is_available():
        return f"Error: {get_error()}"

    query = (query or "").strip()
    if not query and not continuation_id:
        return (
            "Error: nothing to do. Pass a query to start a research, or a continuation_id "
            "to retrieve/resume a previous one."
        )

    max_wait_seconds = max_wait_minutes * 60
    agent = resolve_agent()
    start_time = time.time()

    try:
        if continuation_id:
            existing = client.interactions.get(continuation_id)
            status = getattr(existing, "status", "unknown")
            if status != "completed" or not query:
                return _retrieve(existing, continuation_id, max_wait_seconds, start_time)
            log_progress(f"deep_research: Follow-up on completed interaction {continuation_id}")

        log_progress(f"deep_research: Starting research on '{query[:50]}...' (agent={agent}, v{__version__})")
        create_kwargs = {"input": query, "agent": agent, "background": True}  # background required for agents
        if continuation_id:
            create_kwargs["previous_interaction_id"] = continuation_id
        interaction = client.interactions.create(**create_kwargs)
        interaction_id = interaction.id
        log_progress(f"deep_research: Interaction started (ID: {interaction_id})")

        interaction, message = _wait_for_completion(interaction_id, max_wait_seconds, start_time)
        if message:
            return message
        return _format_report(interaction, query, interaction_id, start_time)

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


def _retrieve(existing, interaction_id: str, max_wait_seconds: int, start_time: float) -> str:
    """Return the report of a previous interaction, waiting while it is still running."""
    status = getattr(existing, "status", "unknown")
    if status == "completed":
        log_progress(f"deep_research: Retrieving completed interaction {interaction_id}")
        interaction = existing
    else:
        log_progress(f"deep_research: Resuming wait on interaction {interaction_id} (status={status})")
        interaction, message = _wait_for_completion(interaction_id, max_wait_seconds, start_time)
        if message:
            return message
    return _format_report(interaction, _original_query(interaction), interaction_id, start_time)


def _wait_for_completion(interaction_id: str, max_wait_seconds: int, start_time: float):
    """Poll until the interaction completes. Returns (interaction, None) or (None, message)."""
    last_status = None
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_seconds:
            return None, timeout_message(interaction_id, max_wait_seconds)

        interaction = client.interactions.get(interaction_id)
        status = getattr(interaction, "status", "unknown")
        if status != last_status:
            log_progress(f"deep_research: Status={status} ({int(elapsed / 60)}m elapsed)")
            last_status = status

        if status == "completed":
            log_progress(f"deep_research: Completed in {int(elapsed)}s")
            return interaction, None
        if status in TERMINAL_FAILURES:
            return None, f"Research {status}: {getattr(interaction, 'error', 'Unknown error')}"

        time.sleep(POLL_INTERVAL_SECONDS)


def timeout_message(interaction_id: str, max_wait_seconds: int) -> str:
    """What to do after a timeout: the research keeps running on Google's side."""
    return (
        f"Research timed out after {max_wait_seconds // 60} minutes. It is still running on Google's side.\n\n"
        f"To get the report, call gemini_deep_research again with continuation_id='{interaction_id}' "
        f"and an EMPTY query: it returns the report if ready, or keeps waiting. "
        f"(Passing a query with that ID would start a follow-up research instead.)"
    )


def _original_query(interaction) -> str:
    """Best-effort: the user_input text of an interaction (for the report header)."""
    for step in getattr(interaction, "steps", None) or []:
        if getattr(step, "type", None) != "user_input":
            continue
        content = getattr(step, "content", None)
        if isinstance(content, str):
            return content
        texts = [getattr(i, "text", "") for i in (content or []) if getattr(i, "text", None)]
        if texts:
            return "".join(texts)
    return "(retrieved from a previous interaction)"


def _format_report(interaction, query: str, interaction_id: str, start_time: float) -> str:
    report = extract_interaction_text(interaction)
    if not report or report == str(interaction):
        return f"Research completed but no output found. ID: {interaction_id}"
    elapsed_mins = round((time.time() - start_time) / 60, 1)
    return (
        "# Deep Research Report\n\n"
        f"**Query:** {query}\n"
        f"**Duration:** {elapsed_mins} minutes\n\n"
        "---\n\n"
        f"{report}"
        f"\n\n---\n*interaction_id: {interaction_id}*"
    )
