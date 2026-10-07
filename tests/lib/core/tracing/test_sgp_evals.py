"""Spans of an SGP evals generation-unit task carry flat ``sgp_evals_*`` keys on the SGP copy.

Expectations come from the contract with sgp-evaluations: the task is created with
``task_metadata = {"sgp_evals": "generation-unit", "generation_run_id", "row_id", "attempt_idx"}``
and its spans must be findable by ``sgp_evals_generation_run_id``, ``sgp_evals_row_id`` and
``sgp_evals_attempt_idx``.
"""

from __future__ import annotations

import uuid
from typing import Any
from datetime import UTC, datetime
from contextlib import ExitStack
from unittest.mock import Mock, AsyncMock, patch

import pytest
from temporalio.worker import StartActivityInput, StartLocalActivityInput

from agentex.types.span import Span
from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.protocol.acp import RPCMethod, CreateTaskParams, SendMessageParams
from agentex.lib.core.tracing import sgp_evals, sgp_evals_interceptor as interceptor
from agentex.types.task_message_content import TextContent
from agentex.lib.sdk.fastacp.impl.sync_acp import SyncACP
from agentex.lib.core.clients.temporal.types import ConflictWorkflowPolicy
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.services.temporal_task_service import TemporalTaskService
from agentex.lib.core.tracing.processors.sgp_tracing_processor import _sgp_metadata

EVAL_METADATA = {
    "sgp_evals": "generation-unit",
    "generation_run_id": "run-42",
    "row_id": "row-7",
    "attempt_idx": 2,
}
EXPECTED_ATTRS = {
    "sgp_evals_generation_run_id": "run-42",
    "sgp_evals_row_id": "row-7",
    "sgp_evals_attempt_idx": 2,
}


@pytest.fixture(autouse=True)
def _clean_registry():
    sgp_evals.clear()
    yield
    sgp_evals.clear()


def _span(trace_id: str = "task-1", task_id: str | None = None, data: Any = None) -> Span:
    return Span(
        id=str(uuid.uuid4()),
        name="s",
        start_time=datetime.now(UTC),
        trace_id=trace_id,
        task_id=task_id,
        data=data,
    )


def _agent() -> Agent:
    return Agent(
        id="a1",
        name="a",
        description="a",
        acp_type="async",
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )


class TestAttrsFromTaskMetadata:
    def test_eval_task_yields_flat_keys(self) -> None:
        assert sgp_evals.span_attrs_from_task_metadata(EVAL_METADATA) == EXPECTED_ATTRS

    @pytest.mark.parametrize("metadata", [None, {}, {"generation_run_id": "run-42"}, {"other": 1}, "x"])
    def test_non_eval_task_yields_nothing(self, metadata: Any) -> None:
        assert sgp_evals.span_attrs_from_task_metadata(metadata) is None


class TestSGPMetadata:
    def test_registered_task_stamps_sgp_copy_not_span_data(self) -> None:
        sgp_evals.register_task_metadata("task-1", EVAL_METADATA)
        span = _span(data={"caller": "kept"})

        metadata = _sgp_metadata(span)

        assert metadata == {"caller": "kept", **EXPECTED_ATTRS}
        assert span.data == {"caller": "kept"}

    def test_matches_on_span_task_id_when_trace_id_differs(self) -> None:
        sgp_evals.register_task_metadata("task-1", EVAL_METADATA)
        assert _sgp_metadata(_span(trace_id="other", task_id="task-1", data={}))["sgp_evals_row_id"] == "row-7"

    def test_other_tasks_and_non_eval_tasks_are_untouched(self) -> None:
        sgp_evals.register_task_metadata("task-1", EVAL_METADATA)
        sgp_evals.register_task_metadata("task-2", {"unrelated": True})
        assert _sgp_metadata(_span(trace_id="task-2", data={"k": 1})) == {"k": 1}
        assert _sgp_metadata(_span(trace_id="task-3", data={"k": 1})) == {"k": 1}

    def test_eval_span_with_list_data_keeps_list_and_gains_the_ids(self) -> None:
        sgp_evals.register_task_metadata("task-1", EVAL_METADATA)
        assert _sgp_metadata(_span(data=[{"a": 1}])) == {**EXPECTED_ATTRS, "data": [{"a": 1}]}

    def test_task_that_stops_being_an_eval_task_stops_being_stamped(self) -> None:
        sgp_evals.register_task_metadata("task-1", EVAL_METADATA)
        sgp_evals.register_task_metadata("task-1", {"team": "x"})
        assert _sgp_metadata(_span(data={"k": 1})) == {"k": 1}

    def test_registry_is_bounded(self) -> None:
        with patch.object(sgp_evals, "_MAX_TASKS", 2):
            for i in range(3):
                sgp_evals.register_task_metadata(f"t{i}", EVAL_METADATA)
        assert sgp_evals.attrs_for_span(_span(trace_id="t0")) == {}
        assert sgp_evals.attrs_for_span(_span(trace_id="t2")) == EXPECTED_ATTRS


class TestAcpServer:
    """Sync and async (base) agents: the ACP server sees the task and spans are emitted in-process."""

    async def _dispatch(self, acp: SyncACP, method: RPCMethod, params: Any) -> Any:
        class _Req:
            headers: dict[str, str] = {}

            async def json(self) -> dict[str, Any]:
                return {"jsonrpc": "2.0", "method": method.value, "params": params.model_dump(mode="json"), "id": "1"}

        return await acp._handle_jsonrpc(_Req())  # pyright: ignore[reportArgumentType]

    async def test_task_create_registers_eval_task(self) -> None:
        acp = SyncACP()
        seen: list[Any] = []

        @acp.on_task_create
        async def handler(params: CreateTaskParams) -> None:
            seen.append(_sgp_metadata(_span(trace_id=params.task.id, data={})))

        task = Task(id="task-1", status="RUNNING", task_metadata=EVAL_METADATA)
        await self._dispatch(acp, RPCMethod.TASK_CREATE, CreateTaskParams(agent=_agent(), task=task, params=None))

        assert seen == [EXPECTED_ATTRS]

    async def test_message_send_registers_eval_task(self) -> None:
        acp = SyncACP()
        seen: list[Any] = []

        @acp.on_message_send
        async def handler(params: SendMessageParams) -> Any:
            seen.append(_sgp_metadata(_span(trace_id=params.task.id, data={})))
            return None

        task = Task(id="task-1", status="RUNNING", task_metadata=EVAL_METADATA)
        params = SendMessageParams(agent=_agent(), task=task, content=TextContent(author="user", content="hi"), stream=False)
        await self._dispatch(acp, RPCMethod.MESSAGE_SEND, params)

        assert seen == [EXPECTED_ATTRS]

    async def test_non_eval_task_is_not_registered(self) -> None:
        acp = SyncACP()

        @acp.on_task_create
        async def handler(params: CreateTaskParams) -> None:
            return None

        task = Task(id="task-1", status="RUNNING", task_metadata={"team": "x"})
        await self._dispatch(acp, RPCMethod.TASK_CREATE, CreateTaskParams(agent=_agent(), task=task, params=None))

        assert sgp_evals.attrs_for_span(_span(trace_id="task-1")) == {}


def _env_vars() -> Mock:
    env_vars = Mock()
    env_vars.WORKFLOW_NAME = "wf"
    env_vars.WORKFLOW_TASK_QUEUE = "q"
    env_vars.WORKFLOW_EXECUTION_TIMEOUT_SECONDS = 0
    return env_vars


class TestTemporal:
    """Temporal agents: attrs ride the workflow memo, then activity headers, into the worker process."""

    async def _submit(self, task_metadata: dict[str, Any] | None) -> dict[str, Any]:
        client = Mock()
        client.start_workflow = AsyncMock(return_value="task-1")
        service = TemporalTaskService(temporal_client=client, env_vars=_env_vars())
        await service.submit_task(
            agent=_agent(), task=Task(id="task-1", task_metadata=task_metadata), params=None
        )
        return client.start_workflow.await_args.kwargs

    async def test_eval_task_workflow_starts_with_attrs_in_memo(self) -> None:
        kwargs = await self._submit(EVAL_METADATA)
        assert kwargs["memo"] == {"sgp_evals_span_attrs": EXPECTED_ATTRS}
        assert kwargs["conflict_policy"] == ConflictWorkflowPolicy.USE_EXISTING

    async def test_non_eval_task_workflow_has_no_memo(self) -> None:
        assert "memo" not in await self._submit({"team": "x"})
        assert "memo" not in await self._submit(None)

    async def test_memo_flows_through_activity_headers_to_worker_registry(self) -> None:
        sent: dict[str, Any] = {}
        next_outbound = Mock()
        next_outbound.start_activity = lambda input: sent.update(headers=input.headers)
        outbound = interceptor._WorkflowOutbound(next_outbound)
        start_input = Mock(spec=StartActivityInput, headers={})

        with patch.object(interceptor.workflow, "memo_value", return_value=EXPECTED_ATTRS):
            outbound.start_activity(start_input)

        inbound_next = Mock()
        inbound_next.execute_activity = AsyncMock(return_value="ok")
        inbound = interceptor._ActivityInbound(inbound_next)
        info = Mock(workflow_id="task-1")
        with patch.object(interceptor.activity, "info", return_value=info):
            await inbound.execute_activity(Mock(headers=sent["headers"]))

        assert sgp_evals.attrs_for_span(_span(trace_id="task-1")) == EXPECTED_ATTRS

    async def test_plain_activity_does_not_inherit_a_reused_workflow_ids_eval_attrs(self) -> None:
        sgp_evals.register_task("task-1", EXPECTED_ATTRS)
        inbound_next = Mock()
        inbound_next.execute_activity = AsyncMock(return_value="ok")
        with patch.object(interceptor.activity, "info", return_value=Mock(workflow_id="task-1")):
            await interceptor._ActivityInbound(inbound_next).execute_activity(Mock(headers={}))

        assert sgp_evals.attrs_for_span(_span(trace_id="task-1")) == {}

    def test_workflow_without_memo_adds_no_header(self) -> None:
        sent: dict[str, Any] = {}
        next_outbound = Mock()
        next_outbound.start_activity = lambda input: sent.update(headers=input.headers)
        start_input = Mock(spec=StartActivityInput, headers={})

        with patch.object(interceptor.workflow, "memo_value", return_value=None):
            interceptor._WorkflowOutbound(next_outbound).start_activity(start_input)

        assert sent["headers"] == {}

    def test_local_activities_get_the_header_too(self) -> None:
        sent: dict[str, Any] = {}
        next_outbound = Mock()
        next_outbound.start_local_activity = lambda input: sent.update(headers=input.headers)
        start_input = Mock(spec=StartLocalActivityInput, headers={})

        with patch.object(interceptor.workflow, "memo_value", return_value=EXPECTED_ATTRS):
            interceptor._WorkflowOutbound(next_outbound).start_local_activity(start_input)

        assert interceptor.ATTRS_HEADER in sent["headers"]

    async def test_worker_runs_with_the_interceptor_ahead_of_agent_interceptors(self) -> None:
        agent_interceptor = interceptor.SGPEvalsInterceptor()
        module = "agentex.lib.core.temporal.workers.worker"
        with ExitStack() as stack:
            stack.enter_context(patch(f"{module}.EnvironmentVariables"))
            stack.enter_context(patch(f"{module}.init_sgp_obs"))
            for name in ("shutdown_sgp_obs", "shutdown_default_span_queue", "shutdown_sync_tracing_processors", "get_temporal_client"):
                stack.enter_context(patch(f"{module}.{name}", new=AsyncMock()))
            worker_cls = stack.enter_context(patch(f"{module}.Worker"))
            worker_cls.return_value.run = AsyncMock()
            worker = AgentexWorker(task_queue="q", interceptors=[agent_interceptor])
            stack.enter_context(patch.object(worker, "start_health_check_server", new=AsyncMock()))
            stack.enter_context(patch.object(worker, "_register_agent", new=AsyncMock()))
            await worker.run(activities=[], workflow=object)

        interceptors = worker_cls.call_args.kwargs["interceptors"]
        assert isinstance(interceptors[0], interceptor.SGPEvalsInterceptor)
        assert interceptors[1:] == [agent_interceptor]
