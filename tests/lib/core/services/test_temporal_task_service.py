"""Unit tests for TemporalTaskService idempotency behavior.

Covers the ``task/create`` idempotency guarantee: duplicate submits for the
same task ID must not raise ``WorkflowAlreadyStartedError``. The service
achieves this by passing ``ConflictWorkflowPolicy.USE_EXISTING`` through the
``TemporalClient`` wrapper, which maps to ``WorkflowIDConflictPolicy.USE_EXISTING``
on the underlying temporalio client so Temporal returns a handle to the
existing run instead of erroring.
"""

from __future__ import annotations

from unittest.mock import Mock, AsyncMock

import pytest
from temporalio.common import WorkflowIDConflictPolicy

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.lib.core.clients.temporal.types import (
    ConflictWorkflowPolicy,
    DuplicateWorkflowPolicy,
)
from agentex.lib.core.clients.temporal.temporal_client import TemporalClient
from agentex.lib.core.temporal.services.temporal_task_service import TemporalTaskService


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


def _env_vars() -> Mock:
    env_vars = Mock()
    env_vars.WORKFLOW_NAME = "test-workflow"
    env_vars.WORKFLOW_TASK_QUEUE = "test-queue"
    env_vars.WORKFLOW_EXECUTION_TIMEOUT_SECONDS = 0
    return env_vars


class TestSubmitTaskIdempotency:
    async def test_submit_task_uses_use_existing_conflict_policy(self) -> None:
        """Duplicate task/create must be idempotent.

        Passing ``ConflictWorkflowPolicy.USE_EXISTING`` tells Temporal to
        return the existing workflow handle instead of raising
        ``WorkflowAlreadyStartedError`` when a run with that ID is already
        active. Without this, load-balanced agentex-agent replicas racing on
        the same task ID surface Temporal's start conflict as an error log.
        """
        temporal_client = Mock()
        temporal_client.start_workflow = AsyncMock(return_value="test-task-123")

        service = TemporalTaskService(temporal_client=temporal_client, env_vars=_env_vars())

        result = await service.submit_task(agent=_agent(), task=_task(), params=None)

        temporal_client.start_workflow.assert_awaited_once()
        kwargs = temporal_client.start_workflow.await_args.kwargs
        assert kwargs["conflict_policy"] == ConflictWorkflowPolicy.USE_EXISTING
        assert kwargs["id"] == "test-task-123"
        assert result == "test-task-123"


class TestTemporalClientConflictPolicyPlumbing:
    """Boundary tests: ``TemporalClient.start_workflow`` wraps
    ``WorkflowIDConflictPolicy`` in a local ``ConflictWorkflowPolicy`` enum
    (mirroring the existing ``DuplicateWorkflowPolicy`` pattern) so SDK users
    don't have to import ``temporalio.common`` to opt into non-default behavior.
    Also guards the incompatible ``TERMINATE_IF_RUNNING`` + explicit-conflict
    combo client-side rather than letting it round-trip to the frontend as
    ``InvalidArgument``.
    """

    async def test_forwards_conflict_policy_when_set(self) -> None:
        inner_client = Mock()
        inner_handle = Mock()
        inner_handle.id = "wf-1"
        inner_client.start_workflow = AsyncMock(return_value=inner_handle)

        tc = TemporalClient(temporal_client=inner_client)

        await tc.start_workflow(
            workflow="w",
            arg={},
            id="id-1",
            task_queue="q",
            conflict_policy=ConflictWorkflowPolicy.USE_EXISTING,
        )

        kwargs = inner_client.start_workflow.await_args.kwargs
        assert kwargs["id_conflict_policy"] == WorkflowIDConflictPolicy.USE_EXISTING

    async def test_default_conflict_policy_is_unspecified(self) -> None:
        inner_client = Mock()
        inner_handle = Mock()
        inner_handle.id = "wf-1"
        inner_client.start_workflow = AsyncMock(return_value=inner_handle)

        tc = TemporalClient(temporal_client=inner_client)

        await tc.start_workflow(workflow="w", arg={}, id="id-1", task_queue="q")

        kwargs = inner_client.start_workflow.await_args.kwargs
        assert kwargs["id_conflict_policy"] == WorkflowIDConflictPolicy.UNSPECIFIED

    async def test_terminate_if_running_with_explicit_conflict_policy_raises(self) -> None:
        """temporalio rejects this combo at the frontend as InvalidArgument;
        we fail fast client-side with a clearer message.
        """
        inner_client = Mock()
        inner_client.start_workflow = AsyncMock()

        tc = TemporalClient(temporal_client=inner_client)

        with pytest.raises(ValueError, match="TERMINATE_EXISTING"):
            await tc.start_workflow(
                workflow="w",
                arg={},
                id="id-1",
                task_queue="q",
                duplicate_policy=DuplicateWorkflowPolicy.TERMINATE_IF_RUNNING,
                conflict_policy=ConflictWorkflowPolicy.USE_EXISTING,
            )

        inner_client.start_workflow.assert_not_awaited()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
