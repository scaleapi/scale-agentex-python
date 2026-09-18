from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

with workflow.unsafe.imports_passed_through():
    from agentex.lib.core.temporal.workflows import workflow as base_workflow


@workflow.defn
class ReplayLoggingWorkflow:
    @workflow.run
    async def run(self) -> None:
        base_workflow.logger.info("SDK workflow replay log")


def completed_history() -> WorkflowHistory:
    return WorkflowHistory.from_json(
        "replay-logging-workflow",
        {
            "events": [
                {
                    "eventId": "1",
                    "eventTime": "2026-09-18T00:00:00Z",
                    "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED",
                    "workflowExecutionStartedEventAttributes": {
                        "workflowType": {"name": "ReplayLoggingWorkflow"},
                        "taskQueue": {"name": "replay-logging-queue"},
                        "workflowTaskTimeout": "10s",
                        "originalExecutionRunId": "806b1959-3829-42a6-a32b-2623ea410033",
                    },
                },
                {
                    "eventId": "2",
                    "eventType": "EVENT_TYPE_WORKFLOW_TASK_SCHEDULED",
                    "workflowTaskScheduledEventAttributes": {
                        "taskQueue": {"name": "replay-logging-queue"},
                        "startToCloseTimeout": "10s",
                        "attempt": 1,
                    },
                },
                {
                    "eventId": "3",
                    "eventTime": "2026-09-18T00:00:00Z",
                    "eventType": "EVENT_TYPE_WORKFLOW_TASK_STARTED",
                    "workflowTaskStartedEventAttributes": {"scheduledEventId": "2"},
                },
                {
                    "eventId": "4",
                    "eventType": "EVENT_TYPE_WORKFLOW_TASK_COMPLETED",
                    "workflowTaskCompletedEventAttributes": {"scheduledEventId": "2", "startedEventId": "3"},
                },
                {
                    "eventId": "5",
                    "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED",
                    "workflowExecutionCompletedEventAttributes": {"workflowTaskCompletedEventId": "4"},
                },
            ],
        },
    )


async def test_sdk_logger_suppresses_real_workflow_replay(caplog, monkeypatch: pytest.MonkeyPatch) -> None:
    caplog.set_level(logging.INFO, logger=base_workflow.logger.name)
    with ThreadPoolExecutor(max_workers=1) as executor:
        replayer = Replayer(workflows=[ReplayLoggingWorkflow], workflow_task_executor=executor)

        with monkeypatch.context() as patch:
            patch.setattr(base_workflow, "logger", logging.getLogger(base_workflow.logger.name))
            await replayer.replay_workflow(completed_history())

        assert [record.getMessage() for record in caplog.records] == ["SDK workflow replay log"]
        caplog.clear()

        await replayer.replay_workflow(completed_history())

    assert not caplog.records
