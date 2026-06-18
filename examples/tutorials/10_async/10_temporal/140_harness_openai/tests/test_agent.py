"""Offline test for the Temporal OpenAI Agents harness tutorial.

This test does NOT require a running Agentex server, Temporal, Redis, or an
OpenAI API key. It verifies the delivery path the harness activity uses: an
``OpenAITurn`` built from an injected canonical stream, pushed through
``UnifiedEmitter.auto_send_turn`` with an injected fake streaming backend,
returns the accumulated final text (which the activity returns to the workflow).

To run: ``pytest tests/test_agent.py -v``
"""

from __future__ import annotations

import pytest

from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.lib.adk.providers._modules.openai_turn import OpenAITurn


class _FakeCtx:
    def __init__(self, initial_content):
        self.task_message = TaskMessage(id="m-1", task_id="task-1", content=initial_content)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        await self.close()
        return False

    async def close(self):
        pass

    async def stream_update(self, update):
        return update


class _FakeStreaming:
    def streaming_task_message_context(self, task_id, initial_content, **_kwargs):  # noqa: ARG002
        return _FakeCtx(initial_content)


async def _canonical_stream(events):
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_activity_delivery_returns_final_text():
    events = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="72")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="F")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = OpenAITurn(stream=_canonical_stream(events), model="gpt-4o")
    emitter = UnifiedEmitter(
        task_id="task-1",
        trace_id=None,
        parent_span_id=None,
        streaming=_FakeStreaming(),
    )

    result = await emitter.auto_send_turn(turn)
    assert result.final_text == "72F"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
