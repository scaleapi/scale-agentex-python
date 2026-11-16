"""A client that disconnects mid-stream must close the handler's generator.

Starlette closes the response body iterator on disconnect. If that iterator
does not close the handler generator it loops over, the handler (and any
harness turn and CLI subprocess under it) stays suspended until garbage
collection, which never happens while something still references it.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, cast

import pytest

from agentex.types.text_delta import TextDelta
from agentex.types.task_message_update import StreamTaskMessageDelta
from agentex.lib.sdk.fastacp.impl.sync_acp import SyncACP


@pytest.mark.asyncio
async def test_closing_the_stream_closes_the_handler_generator() -> None:
    closed: list[bool] = []

    async def handler_stream():
        try:
            for text in ("a", "b", "c"):
                yield StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta=text))
        finally:
            closed.append(True)

    source = handler_stream()
    response = await SyncACP()._handle_streaming_response("req-1", source)
    body = cast(AsyncGenerator[Any, None], response.body_iterator)

    first = await body.__anext__()
    await body.aclose()

    assert '"text_delta":"a"' in str(first)
    assert closed == [True]
