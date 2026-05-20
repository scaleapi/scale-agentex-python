"""Tests for MessagesService created_at forwarding to the SDK client."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from agentex._types import omit
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.lib.core.services.adk.messages import MessagesService

_TS = datetime(2026, 5, 13, 18, 30, 0, tzinfo=timezone.utc)


def _make_task_message() -> TaskMessage:
    return TaskMessage(
        id="m1",
        task_id="t1",
        content=TextContent(author="agent", content="hi", format="markdown"),
        streaming_status="DONE",
    )


def _mock_span():
    span = Mock()
    span.output = None

    async def __aenter__(_self):
        return span

    async def __aexit__(_self, *args):
        return None

    span.__aenter__ = __aenter__
    span.__aexit__ = __aexit__
    return span


def _make_service() -> tuple[AsyncMock, MessagesService]:
    client = AsyncMock()
    streaming = AsyncMock()
    tracer = Mock()
    trace = Mock()
    trace.span.return_value = _mock_span()
    tracer.trace.return_value = trace
    svc = MessagesService(
        agentex_client=client,
        streaming_service=streaming,
        tracer=tracer,
    )
    return client, svc


class TestCreateMessageForwardsCreatedAt:
    async def test_forwards_when_provided(self) -> None:
        client, svc = _make_service()
        client.messages.create.return_value = _make_task_message()

        await svc.create_message(
            task_id="t1",
            content=TextContent(author="user", content="hi", format="markdown"),
            emit_updates=False,
            created_at=_TS,
        )

        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["created_at"] == _TS

    async def test_omits_when_none(self) -> None:
        client, svc = _make_service()
        client.messages.create.return_value = _make_task_message()

        await svc.create_message(
            task_id="t1",
            content=TextContent(author="user", content="hi", format="markdown"),
            emit_updates=False,
        )

        kwargs = client.messages.create.call_args.kwargs
        # The SDK uses an `omit` sentinel for "leave it to the server".
        assert kwargs["created_at"] is omit


class TestBatchForwardsCreatedAt:
    async def test_forwards_when_provided(self) -> None:
        client, svc = _make_service()
        client.messages.batch.create.return_value = [_make_task_message()]

        await svc.create_messages_batch(
            task_id="t1",
            contents=[TextContent(author="user", content="hi", format="markdown")],
            emit_updates=False,
            created_at=_TS,
        )

        kwargs = client.messages.batch.create.call_args.kwargs
        assert kwargs["created_at"] == _TS
