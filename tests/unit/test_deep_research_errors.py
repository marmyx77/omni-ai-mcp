"""
Unit tests for deep_research error reporting and agent resolution (v4.6.4).

Regression: for months a stale install answered "Deep Research Agent not
available" for a retired agent ID, hiding both the API error and the agent.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import __version__
from app.tools.web.deep_research import format_deep_research_error, resolve_agent, extract_interaction_text
from app.services.model_registry import ModelRegistry


AGENT = "deep-research-preview-04-2026"


def test_not_found_names_agent_api_error_and_version():
    msg = format_deep_research_error(Exception("404 NOT_FOUND: agent deep-research-pro-preview not found"), AGENT)
    assert AGENT in msg
    assert "404 NOT_FOUND" in msg
    assert __version__ in msg
    assert "GEMINI_MODEL_DEEP_RESEARCH" in msg
    assert "not available" not in msg.lower()  # the old, opaque wording is gone


def test_not_found_with_continuation_id_blames_the_interaction_not_the_agent():
    msg = format_deep_research_error(Exception("404 NOT_FOUND interaction"), AGENT, interaction_id="v1_abc")
    assert "v1_abc" in msg
    assert "continuation_id" in msg


def test_quota_and_permission_are_distinguished():
    assert "quota" in format_deep_research_error(Exception("429 RESOURCE_EXHAUSTED"), AGENT).lower()
    assert "not allowed" in format_deep_research_error(Exception("403 PERMISSION_DENIED"), AGENT)


def test_unknown_error_is_passed_through_with_footer():
    msg = format_deep_research_error(Exception("boom"), AGENT)
    assert msg.startswith("Error: boom")
    assert f"`{AGENT}`" in msg


def test_agent_is_resolved_per_call_from_the_registry(monkeypatch):
    """A newer agent in the API list wins without a code change or a restart."""
    # app.tools.web.deep_research (the package attribute) is the tool function:
    # the registry re-exports it. Patch the module object itself.
    mod = sys.modules["app.tools.web.deep_research"]
    fake = ModelRegistry()
    fake._available_model_names = [AGENT, "deep-research-preview-11-2026"]
    fake._cache_timestamp = time.time()
    monkeypatch.delenv("GEMINI_MODEL_DEEP_RESEARCH", raising=False)
    monkeypatch.setattr(mod, "model_registry", fake)
    assert resolve_agent() == "deep-research-preview-11-2026"


def test_extract_text_concatenates_all_model_output_steps():
    class Item:
        def __init__(self, text): self.text = text
    class Step:
        def __init__(self, type_, content): self.type = type_; self.content = content
    class Interaction:
        steps = [Step("model_output", [Item("part one. ")]), Step("tool_call", [Item("ignored")]),
                 Step("model_output", [Item("part two.")])]
        output_text = "part two."
    assert extract_interaction_text(Interaction()) == "part one. part two."
