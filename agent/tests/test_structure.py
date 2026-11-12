"""Each of the agent's jobs lives in one module, as docs/CODE_STANDARDS.md asks."""

from pathlib import Path

import pytest

MODULES = sorted(Path(__file__).parent.parent.glob("*.py"))
HOMES = {
    "an HTTP client": ("httpx.Client", "api.py"),
    "a path in the backend's API": ('"/', "api.py"),
    "a tool": ("@tool", "tools.py"),
    "an agent": ("create_agent(", "harness.py"),
    "a model": ("ChatOpenAI(", "harness.py"),
}


@pytest.mark.parametrize(
    ("what", "marker", "home"), [(w, *h) for w, h in HOMES.items()]
)
def test_each_job_has_one_home(what, marker, home):
    found = [m.name for m in MODULES if marker in m.read_text(encoding="utf-8")]
    assert found == [home], f"Only {home} should define {what}"
