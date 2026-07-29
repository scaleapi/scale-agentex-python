from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from agentex.lib.core.tracing.trace import Trace, AsyncTrace
from agentex.lib.core.tracing.baggage import (
    END_USER_ID_SPAN_KEY,
    END_USER_ID_MAX_LENGTH,
    get_baggage,
    get_end_user_id,
    set_end_user_id,
    reset_end_user_id,
    merge_baggage_into_span_data,
)


@pytest.fixture(autouse=True)
def _clear_baggage():
    """Keep contextvar state from leaking between tests in the same task."""
    token = set_end_user_id(None)
    yield
    reset_end_user_id(token)


class TestSetAndGet:
    def test_round_trips_a_value(self):
        set_end_user_id("user-1")
        assert get_end_user_id() == "user-1"

    def test_defaults_to_none(self):
        assert get_end_user_id() is None

    def test_reset_restores_the_previous_value(self):
        set_end_user_id("outer")
        token = set_end_user_id("inner")
        assert get_end_user_id() == "inner"
        reset_end_user_id(token)
        assert get_end_user_id() == "outer"

    def test_strips_surrounding_whitespace(self):
        set_end_user_id("  user-1\n")
        assert get_end_user_id() == "user-1"

    def test_blank_becomes_none(self):
        set_end_user_id("   ")
        assert get_end_user_id() is None

    def test_truncates_to_the_backend_cap(self):
        set_end_user_id("u" * (END_USER_ID_MAX_LENGTH + 50))
        value = get_end_user_id()
        assert value is not None
        assert len(value) == END_USER_ID_MAX_LENGTH

    def test_non_string_is_ignored(self):
        """Defensive: values ultimately originate from a deserialized payload."""
        set_end_user_id(1234)  # type: ignore[arg-type]
        assert get_end_user_id() is None


class TestGetBaggage:
    def test_empty_when_unset(self):
        assert get_baggage() == {}

    def test_carries_the_reserved_key(self):
        set_end_user_id("user-1")
        assert get_baggage() == {END_USER_ID_SPAN_KEY: "user-1"}


class TestMergeBaggageIntoSpanData:
    def test_returns_data_unchanged_when_no_baggage(self):
        data = {"a": 1}
        assert merge_baggage_into_span_data(data) == {"a": 1}

    def test_creates_a_dict_from_none(self):
        set_end_user_id("user-1")
        assert merge_baggage_into_span_data(None) == {END_USER_ID_SPAN_KEY: "user-1"}

    def test_none_stays_none_when_no_baggage(self):
        assert merge_baggage_into_span_data(None) is None

    def test_merges_alongside_existing_keys(self):
        set_end_user_id("user-1")
        assert merge_baggage_into_span_data({"a": 1}) == {END_USER_ID_SPAN_KEY: "user-1", "a": 1}

    def test_explicit_call_site_data_wins(self):
        set_end_user_id("from-baggage")
        merged = merge_baggage_into_span_data({END_USER_ID_SPAN_KEY: "from-call-site"})
        assert merged == {END_USER_ID_SPAN_KEY: "from-call-site"}

    def test_list_data_is_left_alone(self):
        set_end_user_id("user-1")
        data = [{"a": 1}]
        assert merge_baggage_into_span_data(data) == [{"a": 1}]


class TestSpanStamping:
    """The merge has to happen before the span is handed to the processors."""

    def _sync_trace(self) -> Trace:
        return Trace(processors=[], client=MagicMock(), trace_id="trace-1")

    def _async_trace(self) -> AsyncTrace:
        return AsyncTrace(processors=[], client=MagicMock(), trace_id="trace-1")

    def test_sync_start_span_stamps_the_end_user(self):
        set_end_user_id("user-1")
        span = self._sync_trace().start_span(name="foo")
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1"}

    def test_sync_start_span_preserves_call_site_data(self):
        set_end_user_id("user-1")
        span = self._sync_trace().start_span(name="foo", data={"a": 1})
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1", "a": 1}

    def test_sync_start_span_leaves_data_none_without_baggage(self):
        span = self._sync_trace().start_span(name="foo")
        assert span.data is None

    def test_sync_end_span_restamps_data_replaced_wholesale_after_start(self):
        """Agent code may assign span.data outright, dropping what start merged in."""
        trace = self._sync_trace()
        set_end_user_id("user-1")
        span = trace.start_span(name="foo")
        span.data = {"a": 1}
        trace.end_span(span)
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1", "a": 1}

    def test_sync_end_span_keeps_the_value_merged_at_start(self):
        """The ordinary path: the same Span object carries data through to end."""
        trace = self._sync_trace()
        set_end_user_id("user-1")
        span = trace.start_span(name="foo")
        trace.end_span(span)
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1"}

    def test_sync_span_context_manager_stamps_the_end_user(self):
        trace = self._sync_trace()
        set_end_user_id("user-1")
        with trace.span(name="foo") as span:
            assert span is not None
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1"}

    async def test_async_start_span_stamps_the_end_user(self):
        set_end_user_id("user-1")
        span = await self._async_trace().start_span(name="foo")
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1"}

    async def test_async_start_span_preserves_call_site_data(self):
        set_end_user_id("user-1")
        span = await self._async_trace().start_span(name="foo", data={"a": 1})
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1", "a": 1}

    async def test_async_end_span_restamps_data_replaced_wholesale_after_start(self):
        trace = self._async_trace()
        set_end_user_id("user-1")
        span = await trace.start_span(name="foo")
        span.data = {"a": 1}
        await trace.end_span(span)
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1", "a": 1}

    async def test_async_end_span_keeps_the_value_merged_at_start(self):
        trace = self._async_trace()
        set_end_user_id("user-1")
        span = await trace.start_span(name="foo")
        await trace.end_span(span)
        assert span.data == {END_USER_ID_SPAN_KEY: "user-1"}


class TestContextIsolation:
    """The whole point of the contextvar: no cross-request bleed."""

    async def test_concurrent_tasks_do_not_see_each_others_values(self):
        observed: dict[str, str | None] = {}

        async def request(name: str, end_user_id: str) -> None:
            set_end_user_id(end_user_id)
            await asyncio.sleep(0)  # let the other task run and set its own value
            observed[name] = get_end_user_id()

        await asyncio.gather(request("a", "user-a"), request("b", "user-b"))

        assert observed == {"a": "user-a", "b": "user-b"}

    async def test_a_child_tasks_value_does_not_leak_to_the_parent(self):
        set_end_user_id("parent")

        async def child() -> None:
            set_end_user_id("child")

        await asyncio.create_task(child())

        assert get_end_user_id() == "parent"

    async def test_a_task_created_after_set_inherits_the_value(self):
        """Why the ACP server's background request tasks are safe."""
        set_end_user_id("user-1")
        observed: list[str | None] = []

        async def child() -> None:
            observed.append(get_end_user_id())

        await asyncio.create_task(child())

        assert observed == ["user-1"]
