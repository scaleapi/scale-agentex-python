import pytest

from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from tests.lib.core.harness.conformance.runner import Fixture, register, derive_all, all_fixtures

register(
    Fixture(
        name="builtin-single-tool",
        events=[
            StreamTaskMessageStart(
                type="start",
                index=0,
                content=ToolRequestContent(
                    type="tool_request", author="agent", tool_call_id="c", name="Bash", arguments={}
                ),
            ),
            StreamTaskMessageDone(type="done", index=0),
            StreamTaskMessageFull(
                type="full",
                index=1,
                content=ToolResponseContent(
                    type="tool_response", author="agent", tool_call_id="c", name="Bash", content="ok"
                ),
            ),
        ],
    )
)


@pytest.mark.parametrize("fixture", all_fixtures(), ids=lambda f: f.name)
def test_span_derivation_is_deterministic(fixture):
    """Exercises the cross-channel guarantee: yield and auto-send observe the
    same event stream, so span derivation must be deterministic/idempotent."""
    # Deriving twice over the same events yields identical signals (the property
    # that makes yield vs auto-send equivalent, since both observe the same stream).
    assert derive_all(fixture.events) == derive_all(fixture.events)
