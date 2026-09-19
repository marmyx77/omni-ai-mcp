"""
Unit tests for ask_gemini's thinking-parameter selection (v4.6.1).

The knob must be chosen on the RESOLVED model ID: with auto-detect, the
``flash`` alias may point at any generation.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.tools.text.ask_gemini import thinking_params_for, build_thinking_config, THINKING_BUDGETS


@pytest.mark.parametrize("model_id", [
    "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview", "gemini-4.0-pro",
])
def test_gemini_3_plus_uses_thinking_level(model_id):
    assert thinking_params_for(model_id, "high") == {"thinking_level": "high"}


@pytest.mark.parametrize("model_id", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"])
def test_gemini_2x_uses_budget(model_id):
    assert thinking_params_for(model_id, "low") == {"thinking_budget": THINKING_BUDGETS["low"]}
    assert thinking_params_for(model_id, "high") == {"thinking_budget": THINKING_BUDGETS["high"]}


def test_unknown_level_on_2x_falls_back_to_low_budget():
    assert thinking_params_for("gemini-2.5-flash", "bogus") == {"thinking_budget": THINKING_BUDGETS["low"]}


def test_flash_alias_on_a_3x_model_no_longer_sends_a_budget():
    """Regression: the old code keyed on alias == 'pro', so flash → 3.8 got a budget."""
    params = thinking_params_for("gemini-3.8-flash", "low")
    assert "thinking_budget" not in params


def test_medium_is_a_level_on_3x_and_a_budget_on_2x():
    assert thinking_params_for("gemini-3.8-flash", "medium") == {"thinking_level": "medium"}
    assert thinking_params_for("gemini-2.5-flash", "medium") == {"thinking_budget": THINKING_BUDGETS["medium"]}
    assert THINKING_BUDGETS["low"] < THINKING_BUDGETS["medium"] < THINKING_BUDGETS["high"]


@pytest.mark.parametrize("level", ["auto", "off"])
def test_auto_and_off_send_no_thinking_config(level):
    """The model keeps its default. On Gemini 3+ that still means reasoning."""
    assert build_thinking_config("gemini-3.8-flash", level, include_thoughts=False) is None


@pytest.mark.parametrize("level", ["auto", "off"])
def test_auto_with_include_thoughts_still_requests_summaries(level):
    assert build_thinking_config("gemini-3.8-flash", level, include_thoughts=True) == {"include_thoughts": True}


def test_explicit_level_with_thoughts():
    assert build_thinking_config("gemini-3.8-flash", "high", include_thoughts=True) == {
        "include_thoughts": True, "thinking_level": "high",
    }
    assert build_thinking_config("gemini-2.5-pro", "low", include_thoughts=False) == {
        "thinking_budget": THINKING_BUDGETS["low"],
    }
