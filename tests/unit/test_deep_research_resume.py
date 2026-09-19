"""
Unit tests for deep_research retrieve/resume/follow-up (v4.6.5).

Regression: after a timeout the tool told the user to pass continuation_id,
but continuation_id started a NEW chained research — the finished report was
unreachable.
"""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.tools.web.deep_research import deep_research, timeout_message  # noqa: E402

MOD = sys.modules["app.tools.web.deep_research"]
REPORT = "Findings with a source https://example.org/mcp"


def _interaction(id_, status, query="original question", report=REPORT):
    steps = [SimpleNamespace(type="user_input", content=[SimpleNamespace(text=query)])]
    if status == "completed":
        steps.append(SimpleNamespace(type="model_output", content=[SimpleNamespace(text=report)]))
    return SimpleNamespace(id=id_, status=status, steps=steps, error=None)


class FakeInteractions:
    def __init__(self, store):
        self.store = store          # id → list of successive states
        self.created = []

    def get(self, id_):
        states = self.store[id_]
        return states.pop(0) if len(states) > 1 else states[0]

    def create(self, **kwargs):
        self.created.append(kwargs)
        new_id = f"new_{len(self.created)}"
        self.store[new_id] = [_interaction(new_id, "completed", kwargs["input"], "follow-up report")]
        return SimpleNamespace(id=new_id, status="in_progress")


@pytest.fixture
def fake(monkeypatch):
    store = {}
    inter = FakeInteractions(store)
    monkeypatch.setattr(MOD, "client", SimpleNamespace(interactions=inter))
    monkeypatch.setattr(MOD, "is_available", lambda: True)
    monkeypatch.setattr(MOD, "resolve_agent", lambda: "deep-research-preview-04-2026")
    monkeypatch.setattr(MOD.time, "sleep", lambda s: None)
    monkeypatch.delenv("GEMINI_ACTIVITY_LOG", raising=False)
    return inter


def test_no_query_no_id_is_an_error(fake):
    assert deep_research(query="") .startswith("Error: nothing to do")
    assert fake.created == []


def test_retrieve_completed_research_without_starting_a_new_one(fake):
    fake.store["v1_done"] = [_interaction("v1_done", "completed")]
    out = deep_research(query="", continuation_id="v1_done")
    assert "# Deep Research Report" in out
    assert REPORT in out
    assert "**Query:** original question" in out
    assert "interaction_id: v1_done" in out
    assert fake.created == [], "retrieving must not create a new interaction"


def test_resume_waits_while_still_running(fake):
    fake.store["v1_slow"] = [
        _interaction("v1_slow", "in_progress"),   # first get (status check)
        _interaction("v1_slow", "in_progress"),   # first poll
        _interaction("v1_slow", "completed"),     # second poll
    ]
    out = deep_research(query="", continuation_id="v1_slow", max_wait_minutes=5)
    assert REPORT in out
    assert fake.created == []


def test_resume_with_the_same_query_does_not_start_a_follow_up_while_running(fake):
    """Claude will likely repeat the query after a timeout: that must still be a resume."""
    fake.store["v1_slow"] = [_interaction("v1_slow", "in_progress"), _interaction("v1_slow", "completed")]
    out = deep_research(query="original question", continuation_id="v1_slow")
    assert REPORT in out
    assert fake.created == []


def test_follow_up_on_completed_research_chains_a_new_interaction(fake):
    fake.store["v1_done"] = [_interaction("v1_done", "completed")]
    out = deep_research(query="now focus on security", continuation_id="v1_done")
    assert len(fake.created) == 1
    assert fake.created[0]["previous_interaction_id"] == "v1_done"
    assert fake.created[0]["input"] == "now focus on security"
    assert "follow-up report" in out


def test_timeout_message_tells_how_to_retrieve(fake, monkeypatch):
    fake.store["v1_x"] = [_interaction("v1_x", "in_progress")]
    clock = iter([0, 0, 10_000, 10_000, 10_000])
    monkeypatch.setattr(MOD.time, "time", lambda: next(clock))
    out = deep_research(query="", continuation_id="v1_x", max_wait_minutes=5)
    assert out == timeout_message("v1_x", 300)
    assert "EMPTY query" in out


def test_failed_research_is_reported_as_such(fake):
    failed = _interaction("v1_f", "failed")
    failed.error = "agent crashed"
    fake.store["v1_f"] = [failed]
    assert deep_research(query="", continuation_id="v1_f") == "Research failed: agent crashed"


def test_new_research_still_works(fake):
    out = deep_research(query="what is the model context protocol")
    assert fake.created[0]["input"] == "what is the model context protocol"
    assert "previous_interaction_id" not in fake.created[0]
    assert "follow-up report" in out
