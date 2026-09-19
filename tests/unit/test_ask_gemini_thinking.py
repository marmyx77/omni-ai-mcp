"""
Unit tests for ask_gemini's thinking-parameter selection (v4.6.1).

The knob must be chosen on the RESOLVED model ID: with auto-detect, the
``flash`` alias may point at any generation.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.tools.text.ask_gemini import thinking_params_for, THINKING_BUDGETS


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
    assert thinking_params_for("gemini-2.5-flash", "medium") == {"thinking_budget": THINKING_BUDGETS["low"]}


def test_flash_alias_on_a_3x_model_no_longer_sends_a_budget():
    """Regression: the old code keyed on alias == 'pro', so flash → 3.8 got a budget."""
    params = thinking_params_for("gemini-3.8-flash", "low")
    assert "thinking_budget" not in params
