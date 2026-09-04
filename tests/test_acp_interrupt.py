"""Unit tests for the hand-editable task/interrupt additions.

Covers the regeneration-safe surfaces added for the interrupt-and-queue design
(design doc sections 6, 7, 9.2):

1. Protocol (``agentex.protocol.acp``): ``RPCMethod.TASK_INTERRUPT``, the
   ``InterruptTaskParams`` model (mirror of ``CancelTaskParams``), and the
   ``PARAMS_MODEL_BY_METHOD`` entry, plus the back-compat shim re-export.
2. ACP server routing: ``BaseACPServer.on_task_interrupt`` registers a handler
   under ``RPCMethod.TASK_INTERRUPT``.
3. Temporal transport: ``BaseWorkflow.on_interrupt`` is a ``@workflow.signal``
   named ``interrupt_turn`` (and is NOT abstract, so existing agents keep
   working), and ``TemporalTaskService.interrupt`` forwards that signal without
   tearing the workflow down.
"""

from __future__ import annotations

from unittest.mock import Mock, AsyncMock

import pytest

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.protocol.acp import (
    PARAMS_MODEL_BY_METHOD,
    RPCMethod,
    CancelTaskParams,
    InterruptTaskParams,
)


def _agent() -> Agent:
    return Agent(
        id="test-agent-456",
        name="test-agent",
        description="test-agent",
        acp_type="async",
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )


def _task() -> Task:
    return Task(id="test-task-123", status="RUNNING")


# ---------------------------------------------------------------------------
# Protocol additions
# ---------------------------------------------------------------------------


class TestInterruptProtocol:
    def test_rpc_method_value(self) -> None:
        assert RPCMethod.TASK_INTERRUPT.value == "task/interrupt"
        # Constructible from the wire string (the ACP server does RPCMethod(str)).
        assert RPCMethod("task/interrupt") is RPCMethod.TASK_INTERRUPT

    def test_params_model_registered(self) -> None:
        assert PARAMS_MODEL_BY_METHOD[RPCMethod.TASK_INTERRUPT] is InterruptTaskParams

    def test_params_mirror_cancel_shape(self) -> None:
        """InterruptTaskParams mirrors CancelTaskParams field-for-field."""
        assert set(InterruptTaskParams.model_fields) == set(CancelTaskParams.model_fields)
        assert set(InterruptTaskParams.model_fields) == {"agent", "task", "request"}

    def test_params_validate_round_trip(self) -> None:
        params = InterruptTaskParams(agent=_agent(), task=_task())
        assert params.task.id == "test-task-123"
        assert params.request is None
        # Header forwarding path (BaseACPServer populates params.request).
        with_headers = InterruptTaskParams.model_validate(
            {
                "agent": _agent().model_dump(),
                "task": _task().model_dump(),
                "request": {"headers": {"x-foo": "bar"}},
            }
        )
        assert with_headers.request == {"headers": {"x-foo": "bar"}}

    def test_shim_reexports_interrupt_params(self) -> None:
        """The back-compat shim must re-export the new model as the same object."""
        from agentex.protocol import acp as canon
        from agentex.lib.types import acp as shim

        assert shim.InterruptTaskParams is canon.InterruptTaskParams


# ---------------------------------------------------------------------------
# ACP server routing
# ---------------------------------------------------------------------------


class TestACPServerInterruptRouting:
    def test_on_task_interrupt_registers_handler(self) -> None:
        from unittest.mock import patch

        from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer

        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer()

        assert RPCMethod.TASK_INTERRUPT not in server._handlers

        @server.on_task_interrupt
        async def _handle(params: InterruptTaskParams) -> None:  # noqa: ARG001
            return None

        assert RPCMethod.TASK_INTERRUPT in server._handlers
        assert server._handlers[RPCMethod.TASK_INTERRUPT] is not None

    def test_temporal_acp_wires_interrupt_handler(self) -> None:
        from unittest.mock import patch

        from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP

        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = TemporalACP.create(temporal_address="localhost:7233")

        assert RPCMethod.TASK_INTERRUPT in server._handlers


# ---------------------------------------------------------------------------
# Temporal transport: signal + service forwarding
# ---------------------------------------------------------------------------


class TestWorkflowInterruptSignal:
    def test_on_interrupt_is_signal_named_interrupt_turn(self) -> None:
        from agentex.lib.core.temporal.types.workflow import SignalName
        from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow

        # getattr avoids the dunder name-mangling that would otherwise rewrite
        # this to _TestWorkflowInterruptSignal__temporal_signal_definition.
        sd = getattr(BaseWorkflow.on_interrupt, "__temporal_signal_definition")
        assert sd is not None
        # str-enum: equal by value to the wire string "interrupt_turn".
        assert sd.name == SignalName.INTERRUPT_TURN
        assert sd.name == "interrupt_turn"

    def test_on_interrupt_not_abstract(self) -> None:
        """A default no-op keeps existing (non-interruptible) workflows valid."""
        from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow

        assert "on_interrupt" not in BaseWorkflow.__abstractmethods__


class TestTemporalTaskServiceInterrupt:
    async def test_interrupt_sends_signal_not_cancel(self) -> None:
        from agentex.lib.core.temporal.types.workflow import SignalName
        from agentex.lib.core.temporal.services.temporal_task_service import (
            TemporalTaskService,
        )

        temporal_client = Mock()
        temporal_client.send_signal = AsyncMock()
        temporal_client.cancel_workflow = AsyncMock()
        temporal_client.terminate_workflow = AsyncMock()

        service = TemporalTaskService(temporal_client=temporal_client, env_vars=Mock())

        await service.interrupt(agent=_agent(), task=_task(), request={"headers": {"x-a": "b"}})

        # Non-terminal: it signals, it does NOT cancel or terminate the workflow.
        temporal_client.cancel_workflow.assert_not_called()
        temporal_client.terminate_workflow.assert_not_called()
        temporal_client.send_signal.assert_awaited_once()

        kwargs = temporal_client.send_signal.await_args.kwargs
        assert kwargs["workflow_id"] == "test-task-123"
        assert kwargs["signal"] == SignalName.INTERRUPT_TURN.value == "interrupt_turn"
        # Payload is a serialized InterruptTaskParams (task/agent/request).
        assert kwargs["payload"]["task"]["id"] == "test-task-123"
        assert kwargs["payload"]["request"] == {"headers": {"x-a": "b"}}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
