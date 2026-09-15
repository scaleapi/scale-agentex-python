"""The openai-agents scaffolds must not disable tracing outright.

`set_tracing_disabled(True)` stops openai-agents producing spans AT ALL, which
silently starves any processor registered later — including the sgp-obs bridge the SDK
installs when observability is on. The bridge still reports itself installed, so a
Runner turn contributes no model spans and nothing says why.

Measured against a spy processor:

    set_tracing_disabled(True)  -> processors ['BatchTraceProcessor', 'Spy'], spy saw 0
    set_trace_processors([])    -> processors ['Spy'],                        spy saw 1

Note the first row: disabling tracing leaves the OpenAI exporter REGISTERED, merely
never fed. Clearing the list actually removes it, so the replacement is strictly better
at the thing the original was trying to do — keep traces away from api.openai.com.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def _templates_using_agents_tracing() -> list[Path]:
    return sorted(
        p for p in TEMPLATES.rglob("*.j2") if "set_trace_processors" in p.read_text()
    )


def test_some_templates_were_found():
    """Guards the glob itself: if the templates move, the assertions below would
    vacuously pass on an empty list."""
    assert _templates_using_agents_tracing(), f"no templates found under {TEMPLATES}"


@pytest.mark.parametrize(
    "template", _templates_using_agents_tracing(), ids=lambda p: p.parent.parent.name
)
class TestOpenAIAgentsScaffolds:
    def test_does_not_disable_tracing(self, template: Path):
        text = template.read_text()
        assert "set_tracing_disabled(" not in text, (
            f"{template} disables openai-agents tracing, which starves the sgp-obs bridge"
        )

    def test_clears_the_processor_list_instead(self, template: Path):
        assert "set_trace_processors([])" in template.read_text()

    def test_imports_what_it_calls(self, template: Path):
        text = template.read_text()
        assert "set_trace_processors" in text.split("\n\n")[0] or any(
            "import" in line and "set_trace_processors" in line
            for line in text.splitlines()
        ), f"{template} calls set_trace_processors without importing it"
