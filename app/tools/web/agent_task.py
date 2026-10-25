"""
Antigravity Agent Tool (Gemini Managed Agents, v4.8.0)

Delegates a multi-step task to Google's Antigravity agent: it plans, runs
Bash/Python/Node, reads and writes files, searches and reads the web, inside a
Linux sandbox hosted by Google, and returns its final answer. Files persist in
the sandbox across turns of the same conversation (continuation_id).

Modes (same pattern as gemini_deep_research):
- task only: start a new agent run
- continuation_id + task: next turn in the same sandbox
- continuation_id + empty task: retrieve/resume a run that timed out
"""

import os
from typing import List, Optional

from ...tools.registry import tool
from ...services import MODELS, is_available, get_error
from ...services.model_registry import model_registry
from ...services import interactions as ix

TOOLS = ("code_execution", "google_search", "url_context")
POLL_SECONDS = 10

AGENT_SCHEMA = {
    "type": "object",
    "properties": {
        "task": {"type": "string", "description": "What the agent should accomplish. Leave empty with continuation_id to retrieve a run that timed out."},
        "continuation_id": {"type": "string", "description": "interaction_id of a previous run: continue in the same sandbox (files persist), or retrieve it if task is empty."},
        "file_paths": {"type": "array", "items": {"type": "string"}, "description": "Local images/PDF/audio/video to hand to the agent."},
        "tools": {"type": "array", "items": {"type": "string", "enum": list(TOOLS)}, "description": "Restrict the built-in tools (default: all three plus the sandbox filesystem)."},
        "model": {"type": "string", "enum": ["flash", "pro"], "default": "flash", "description": "Brain of the agent: flash (default, the agent's own default) or pro (newest flagship, slower and pricier)."},
        "output_dir": {"type": "string", "description": "Save images/documents/audio/video the agent returns into this folder."},
        "max_wait_minutes": {"type": "integer", "minimum": 1, "maximum": 60, "default": 30}
    }
}


def build_agent_request(agent_id: str, task: str, file_blocks: List[dict], tools: Optional[List[str]],
                        model: str, continuation_id: Optional[str]) -> dict:
    if tools:
        bad = [t for t in tools if t not in TOOLS]
        if bad:
            raise ValueError(f"unknown tools {bad}; allowed: {TOOLS}")
    text = {"type": "text", "text": task.strip()}
    request = {
        "agent": agent_id,
        "input": list(file_blocks) + [text] if file_blocks else task.strip(),
        "environment": "remote",
        "background": True,
    }
    if tools:
        request["tools"] = [{"type": t} for t in tools]
    if model == "pro":
        request["agent_config"] = {"type": "antigravity", "model": MODELS["pro"]}
    if continuation_id:
        request["previous_interaction_id"] = continuation_id
    return request


def _save_outputs(interaction, output_dir: Optional[str]) -> List[str]:
    if not output_dir:
        return []
    saved = []
    for kind in ("image", "document", "audio", "video"):
        for n, item in enumerate(i for i in ix._model_output_items(interaction) if ix._get(i, "type") == kind):
            name = ix._get(item, "name") or f"agent_{kind}_{n}"
            path, _ = ix.save_media(item, os.path.join(output_dir, os.path.basename(str(name))), f"agent_{kind}")
            saved.append(path)
    return saved


def _result(interaction, output_dir: Optional[str]) -> str:
    text = ix.output_text(interaction) or "(the agent returned no text)"
    lines = [text, "", "---", f"*interaction_id / continuation_id: {ix._get(interaction, 'id')}*"]
    usage = ix.usage_line(interaction)
    if usage:
        lines.append(f"*{usage}*")
    for path in _save_outputs(interaction, output_dir):
        lines.append(f"*saved: {path}*")
    return "\n".join(lines)


@tool(
    name="gemini_agent_task",
    description=(
        "Delegate a multi-step task to Google's Antigravity agent, which works in its own Google-hosted Linux sandbox: "
        "runs Bash/Python/Node, installs packages, reads/writes files, searches and reads the web, then reports back. "
        "Continue in the same sandbox with continuation_id (files persist). Long runs: retrieve with continuation_id and an empty task."
    ),
    input_schema=AGENT_SCHEMA,
    tags=["agent", "code", "web"]
)
def agent_task(
    task: str = "",
    continuation_id: Optional[str] = None,
    file_paths: Optional[List[str]] = None,
    tools: Optional[List[str]] = None,
    model: str = "flash",
    output_dir: Optional[str] = None,
    max_wait_minutes: int = 30,
) -> str:
    """Run (or continue, or retrieve) an Antigravity agent task."""
    if not is_available():
        return f"Error: {get_error()}"
    task = (task or "").strip()
    if not task and not continuation_id:
        return "Error: nothing to do. Pass a task, or a continuation_id to retrieve a previous run."
    timeout = max(1, int(max_wait_minutes)) * 60
    uploaded: List[Optional[str]] = []
    try:
        if continuation_id and not task:
            return _result(ix.wait(continuation_id, timeout, POLL_SECONDS), output_dir)
        blocks = []
        for path in file_paths or []:
            block, name = ix.file_block(path)
            blocks.append(block)
            uploaded.append(name)
        request = build_agent_request(model_registry.resolve("agent"), task, blocks, tools, model, continuation_id)
        return _result(ix.run(request, timeout, POLL_SECONDS), output_dir)
    except FileNotFoundError as e:
        return f"Error: file not found: {e}"
    except ValueError as e:
        return f"Error: {e}"
    except ix.InteractionTimeout as t:
        return (f"Agent still working after {t.waited_seconds // 60} min (it keeps running on Google's side).\n"
                f"Call gemini_agent_task again with continuation_id='{t.interaction_id}' and an EMPTY task to get the result.")
    except Exception as e:
        return f"Agent error: {e}"
    finally:
        ix.cleanup(uploaded)
