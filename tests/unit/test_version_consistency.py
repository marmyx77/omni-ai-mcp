"""
Every place that states the package version must agree with pyproject.toml.

CI-enforced because two of these drifted silently for months (README badge
stuck at 4.4.0, .claude-plugin/plugin.json at 4.0.6 — found 2026-09-19).
scripts/bump_version.sh keeps them in sync; this test proves it did.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def _pyproject_version() -> str:
    return re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1)


def _readme_badge_version() -> str:
    m = re.search(r"badge/version-([0-9.]+)-green\.svg", (ROOT / "README.md").read_text())
    assert m, "README version badge not found"
    return m.group(1)


def _claude_md_versions() -> list:
    text = (ROOT / "CLAUDE.md").read_text()
    header = re.search(r"^\*\*Version:\*\* ([0-9.]+)", text, re.M)
    heading = re.search(r"^## Architecture \(v([0-9.]+)\)", text, re.M)
    assert header and heading, "CLAUDE.md version header / Architecture heading not found"
    return [header.group(1), heading.group(1)]


CASES = {
    "app/__init__.py": lambda: __import__("app").__version__,
    "app/core/config.py": lambda: __import__("app.core.config", fromlist=["config"]).config.version,
    "manifest.json": lambda: json.loads((ROOT / "manifest.json").read_text())["version"],
    ".claude-plugin/plugin.json": lambda: json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"],
    "README.md badge": _readme_badge_version,
    "CLAUDE.md header": lambda: _claude_md_versions()[0],
    "CLAUDE.md architecture heading": lambda: _claude_md_versions()[1],
}


@pytest.mark.parametrize("where", list(CASES))
def test_version_matches_pyproject(where):
    assert CASES[where]() == _pyproject_version(), f"{where} is out of sync with pyproject.toml"
