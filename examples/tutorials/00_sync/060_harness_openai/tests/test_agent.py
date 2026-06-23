"""Offline test for the sync OpenAI Agents harness tutorial.

This test does NOT require a running Agentex server or an OpenAI API key. It
verifies the harness wiring this tutorial demonstrates: an ``OpenAITurn`` built
from an injected canonical ``StreamTaskMessage*`` stream, forwarded through
``UnifiedEmitter.yield_turn`` (the sync HTTP ACP delivery path), passes the
events through unchanged.

To run: ``pytest tests/test_agent.py -v``
"""

from __future__ import annotations

import pytest

from agentex.types.text_content import TextContent
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.lib.adk.providers._modules.openai_turn import OpenAITurn


async def _canonical_stream(events):
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_yield_turn_forwards_canonical_stream():
    events = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="Hi")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = OpenAITurn(stream=_canonical_stream(events), model="gpt-4o")
    # trace_id=None disables tracing, so no Agentex server is needed.
    emitter = UnifiedEmitter(task_id="task-1", trace_id=None, parent_span_id=None)

    out = [e async for e in emitter.yield_turn(turn)]
    assert out == events


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
