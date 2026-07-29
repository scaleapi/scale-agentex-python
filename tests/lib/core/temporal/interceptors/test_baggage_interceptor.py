from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.converter import default

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.protocol.acp import CreateTaskParams
from agentex.lib.core.tracing.baggage import get_end_user_id, set_end_user_id, reset_end_user_id
from agentex.lib.core.temporal.workers.worker import _with_default_interceptors
from agentex.lib.core.temporal.interceptors.baggage_interceptor import (
    END_USER_ID_HEADER,
    DISABLE_TRACE_BAGGAGE_ENV,
    TraceBaggageInterceptor,
    _extract_end_user_id,
    trace_baggage_disabled,
    _TraceBaggageActivityInboundInterceptor,
    _TraceBaggageWorkflowInboundInterceptor,
    _TraceBaggageWorkflowOutboundInterceptor,
)

MODULE = "agentex.lib.core.temporal.interceptors.baggage_interceptor"

PAYLOAD_CONVERTER = default().payload_converter


@pytest.fixture(autouse=True)
def _clear_baggage():
    token = set_end_user_id(None)
    yield
    reset_end_user_id(token)


def _create_task_params(end_user_id: str | None) -> CreateTaskParams:
    return CreateTaskParams(
        agent=Agent(
            id="agent-1",
            name="agent",
            acp_type="async",
            description="test agent",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        ),
        task=Task(id="task-1", status="RUNNING"),
        end_user_id=end_user_id,
    )


class TestExtractEndUserId:
    def test_reads_from_a_params_model(self):
        assert _extract_end_user_id(_create_task_params("user-1")) == "user-1"

    def test_reads_from_a_dumped_dict(self):
        assert _extract_end_user_id({"end_user_id": "user-1"}) == "user-1"

    def test_none_arg(self):
        assert _extract_end_user_id(None) is None

    def test_missing_field(self):
        assert _extract_end_user_id({"task": {}}) is None

    def test_null_field(self):
        assert _extract_end_user_id(_create_task_params(None)) is None

    def test_empty_string_is_treated_as_absent(self):
        assert _extract_end_user_id({"end_user_id": ""}) is None

    def test_non_string_is_treated_as_absent(self):
        assert _extract_end_user_id({"end_user_id": 123}) is None


class TestWorkflowInbound:
    def _interceptor(self) -> tuple[_TraceBaggageWorkflowInboundInterceptor, Any, SimpleNamespace]:
        next_inbound = AsyncMock()
        instance = SimpleNamespace()
        return _TraceBaggageWorkflowInboundInterceptor(next_inbound), next_inbound, instance

    async def test_execute_workflow_stashes_the_end_user_on_the_instance(self):
        interceptor, next_inbound, instance = self._interceptor()
        input = SimpleNamespace(args=[_create_task_params("user-1")])

        with patch(f"{MODULE}.workflow.instance", return_value=instance):
            await interceptor.execute_workflow(input)  # type: ignore[arg-type]

        assert instance._agentex_end_user_id == "user-1"
        next_inbound.execute_workflow.assert_called_once_with(input)

    async def test_execute_workflow_stashes_nothing_when_absent(self):
        interceptor, _next, instance = self._interceptor()
        input = SimpleNamespace(args=[_create_task_params(None)])

        with patch(f"{MODULE}.workflow.instance", return_value=instance):
            await interceptor.execute_workflow(input)  # type: ignore[arg-type]

        assert not hasattr(instance, "_agentex_end_user_id")

    async def test_execute_workflow_tolerates_empty_args(self):
        interceptor, next_inbound, instance = self._interceptor()
        input = SimpleNamespace(args=[])

        with patch(f"{MODULE}.workflow.instance", return_value=instance):
            await interceptor.execute_workflow(input)  # type: ignore[arg-type]

        next_inbound.execute_workflow.assert_called_once_with(input)

    async def test_signal_overwrites_the_stashed_end_user(self):
        interceptor, _next, instance = self._interceptor()

        with patch(f"{MODULE}.workflow.instance", return_value=instance):
            await interceptor.execute_workflow(SimpleNamespace(args=[_create_task_params("creator")]))  # type: ignore[arg-type]
            await interceptor.handle_signal(SimpleNamespace(args=[{"end_user_id": "signaller"}]))  # type: ignore[arg-type]

        assert instance._agentex_end_user_id == "signaller"

    async def test_signal_without_an_end_user_keeps_the_existing_one(self):
        interceptor, _next, instance = self._interceptor()

        with patch(f"{MODULE}.workflow.instance", return_value=instance):
            await interceptor.execute_workflow(SimpleNamespace(args=[_create_task_params("creator")]))  # type: ignore[arg-type]
            await interceptor.handle_signal(SimpleNamespace(args=[{"end_user_id": None}]))  # type: ignore[arg-type]

        assert instance._agentex_end_user_id == "creator"

    async def test_a_failure_to_stash_does_not_break_the_workflow(self):
        interceptor, next_inbound, _instance = self._interceptor()
        input = SimpleNamespace(args=[_create_task_params("user-1")])

        with patch(f"{MODULE}.workflow.instance", side_effect=RuntimeError("not in a workflow")):
            await interceptor.execute_workflow(input)  # type: ignore[arg-type]

        next_inbound.execute_workflow.assert_called_once_with(input)


class TestWorkflowOutbound:
    def _interceptor(self) -> tuple[_TraceBaggageWorkflowOutboundInterceptor, Any]:
        next_outbound = MagicMock()
        return _TraceBaggageWorkflowOutboundInterceptor(next_outbound, PAYLOAD_CONVERTER), next_outbound

    def _decode(self, input: Any) -> str:
        return PAYLOAD_CONVERTER.from_payload(input.headers[END_USER_ID_HEADER], str)

    def test_start_activity_adds_the_header(self):
        interceptor, next_outbound = self._interceptor()
        input = SimpleNamespace(headers=None)

        with patch(f"{MODULE}.workflow.instance", return_value=SimpleNamespace(_agentex_end_user_id="user-1")):
            interceptor.start_activity(input)  # type: ignore[arg-type]

        assert self._decode(input) == "user-1"
        next_outbound.start_activity.assert_called_once_with(input)

    def test_start_local_activity_adds_the_header(self):
        interceptor, next_outbound = self._interceptor()
        input = SimpleNamespace(headers=None)

        with patch(f"{MODULE}.workflow.instance", return_value=SimpleNamespace(_agentex_end_user_id="user-1")):
            interceptor.start_local_activity(input)  # type: ignore[arg-type]

        assert self._decode(input) == "user-1"
        next_outbound.start_local_activity.assert_called_once_with(input)

    def test_existing_headers_are_preserved(self):
        interceptor, _next = self._interceptor()
        other = PAYLOAD_CONVERTER.to_payload("keep-me")
        input = SimpleNamespace(headers={"other": other})

        with patch(f"{MODULE}.workflow.instance", return_value=SimpleNamespace(_agentex_end_user_id="user-1")):
            interceptor.start_activity(input)  # type: ignore[arg-type]

        assert input.headers["other"] is other
        assert self._decode(input) == "user-1"

    def test_no_header_when_nothing_is_stashed(self):
        interceptor, next_outbound = self._interceptor()
        input = SimpleNamespace(headers=None)

        with patch(f"{MODULE}.workflow.instance", return_value=SimpleNamespace()):
            interceptor.start_activity(input)  # type: ignore[arg-type]

        assert input.headers is None
        next_outbound.start_activity.assert_called_once_with(input)

    def test_a_failure_to_stamp_does_not_break_the_activity(self):
        interceptor, next_outbound = self._interceptor()
        input = SimpleNamespace(headers=None)

        with patch(f"{MODULE}.workflow.instance", side_effect=RuntimeError("boom")):
            interceptor.start_activity(input)  # type: ignore[arg-type]

        next_outbound.start_activity.assert_called_once_with(input)

    def test_inbound_init_installs_the_outbound_interceptor(self):
        next_inbound = MagicMock()
        interceptor = _TraceBaggageWorkflowInboundInterceptor(next_inbound)

        interceptor.init(MagicMock())

        installed = next_inbound.init.call_args.args[0]
        assert isinstance(installed, _TraceBaggageWorkflowOutboundInterceptor)


class TestActivityInbound:
    def _interceptor(self, observed: list[str | None]) -> _TraceBaggageActivityInboundInterceptor:
        next_inbound = MagicMock()

        async def execute_activity(_input: Any) -> str:
            observed.append(get_end_user_id())
            return "result"

        next_inbound.execute_activity = execute_activity
        return _TraceBaggageActivityInboundInterceptor(next_inbound, PAYLOAD_CONVERTER)

    async def test_header_is_visible_to_the_activity(self):
        observed: list[str | None] = []
        interceptor = self._interceptor(observed)
        headers = {END_USER_ID_HEADER: PAYLOAD_CONVERTER.to_payload("user-1")}

        result = await interceptor.execute_activity(SimpleNamespace(headers=headers))  # type: ignore[arg-type]

        assert result == "result"
        assert observed == ["user-1"]

    async def test_context_is_reset_after_the_activity(self):
        interceptor = self._interceptor([])
        headers = {END_USER_ID_HEADER: PAYLOAD_CONVERTER.to_payload("user-1")}

        await interceptor.execute_activity(SimpleNamespace(headers=headers))  # type: ignore[arg-type]

        assert get_end_user_id() is None

    async def test_context_is_reset_even_when_the_activity_raises(self):
        next_inbound = MagicMock()

        async def boom(_input: Any) -> None:
            raise ValueError("activity failed")

        next_inbound.execute_activity = boom
        interceptor = _TraceBaggageActivityInboundInterceptor(next_inbound, PAYLOAD_CONVERTER)
        headers = {END_USER_ID_HEADER: PAYLOAD_CONVERTER.to_payload("user-1")}

        with pytest.raises(ValueError, match="activity failed"):
            await interceptor.execute_activity(SimpleNamespace(headers=headers))  # type: ignore[arg-type]

        assert get_end_user_id() is None

    async def test_no_header_leaves_the_context_alone(self):
        observed: list[str | None] = []
        interceptor = self._interceptor(observed)

        await interceptor.execute_activity(SimpleNamespace(headers=None))  # type: ignore[arg-type]

        assert observed == [None]

    async def test_an_undecodable_header_does_not_break_the_activity(self):
        observed: list[str | None] = []
        interceptor = self._interceptor(observed)
        headers = {END_USER_ID_HEADER: "not-a-payload"}

        result = await interceptor.execute_activity(SimpleNamespace(headers=headers))  # type: ignore[arg-type]

        assert result == "result"
        assert observed == [None]


class TestDefaultRegistration:
    def test_registered_by_default(self, monkeypatch):
        monkeypatch.delenv(DISABLE_TRACE_BAGGAGE_ENV, raising=False)
        assert any(isinstance(i, TraceBaggageInterceptor) for i in _with_default_interceptors([]))

    def test_placed_before_user_interceptors(self, monkeypatch):
        monkeypatch.delenv(DISABLE_TRACE_BAGGAGE_ENV, raising=False)
        user = MagicMock()
        result = _with_default_interceptors([user])
        assert isinstance(result[0], TraceBaggageInterceptor)
        assert result[1] is user

    def test_not_duplicated_when_already_supplied(self, monkeypatch):
        monkeypatch.delenv(DISABLE_TRACE_BAGGAGE_ENV, raising=False)
        mine = TraceBaggageInterceptor()
        result = _with_default_interceptors([mine])
        assert result == [mine]

    def test_the_input_list_is_not_mutated(self, monkeypatch):
        monkeypatch.delenv(DISABLE_TRACE_BAGGAGE_ENV, raising=False)
        supplied: list[Any] = []
        _with_default_interceptors(supplied)
        assert supplied == []

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", " On "])
    def test_kill_switch_removes_it(self, monkeypatch, value):
        monkeypatch.setenv(DISABLE_TRACE_BAGGAGE_ENV, value)
        assert trace_baggage_disabled() is True
        assert _with_default_interceptors([]) == []

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_other_values_keep_it_enabled(self, monkeypatch, value):
        monkeypatch.setenv(DISABLE_TRACE_BAGGAGE_ENV, value)
        assert trace_baggage_disabled() is False
        assert any(isinstance(i, TraceBaggageInterceptor) for i in _with_default_interceptors([]))
