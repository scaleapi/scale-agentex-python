from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from temporalio import workflow
from temporalio.testing import ActivityEnvironment

from agentex.lib.core.temporal.workflows import workflow as base_workflow
from agentex.lib.core.temporal.plugins.openai_agents.interceptors import context_interceptor


@pytest.fixture(params=[base_workflow.logger, context_interceptor.logger], ids=["base-workflow", "context-interceptor"])
def sdk_logger(request, caplog):
    logger = request.param
    caplog.set_level(logging.DEBUG, logger=logger.name)
    return logger


@pytest.fixture
def workflow_context(monkeypatch):
    def set_context(*, replaying: bool) -> None:
        monkeypatch.setattr(workflow, "in_workflow", lambda: True)
        monkeypatch.setattr(workflow, "info", lambda: SimpleNamespace(workflow_id="task-123", run_id="run-456"))
        replay_check = (
            "is_replaying_history_events" if hasattr(workflow.unsafe, "is_replaying_history_events") else "is_replaying"
        )
        monkeypatch.setattr(workflow.unsafe, replay_check, lambda: replaying)

    return set_context


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR])
def test_sdk_workflow_logs_are_suppressed_during_replay(sdk_logger, workflow_context, caplog, level):
    workflow_context(replaying=True)

    sdk_logger.log(level, "Repeated workflow operation")

    assert not caplog.records


def test_sdk_workflow_logs_include_ids_and_preserve_caller_fields(sdk_logger, workflow_context, caplog):
    workflow_context(replaying=False)
    fields = {"operation": "interrupt", "trace_id": "existing-trace", "span_id": "existing-span"}

    sdk_logger.info("Handling %s", "interrupt", extra=fields)

    (record,) = caplog.records
    assert record.workflow_id == "task-123"
    assert record.run_id == "run-456"
    assert record.operation == "interrupt"
    assert record.trace_id == "existing-trace"
    assert record.span_id == "existing-span"
    assert record.getMessage() == "Handling interrupt"
    assert record.pathname == __file__
    assert "temporal_workflow" not in record.__dict__
    assert fields == {"operation": "interrupt", "trace_id": "existing-trace", "span_id": "existing-span"}


def test_workflow_logs_without_trace_context_do_not_invent_ids(sdk_logger, workflow_context, caplog):
    workflow_context(replaying=False)

    sdk_logger.info("Workflow without a trace")

    (record,) = caplog.records
    assert record.workflow_id == "task-123"
    assert record.run_id == "run-456"
    assert "trace_id" not in record.__dict__
    assert "span_id" not in record.__dict__


@pytest.mark.parametrize("in_activity", [False, True], ids=["startup", "activity"])
def test_sdk_logger_works_outside_workflows(sdk_logger, caplog, in_activity):
    def log_message():
        sdk_logger.info("Outside workflow", extra={"operation": "startup"})

    if in_activity:
        ActivityEnvironment().run(log_message)
    else:
        log_message()

    (record,) = caplog.records
    assert record.getMessage() == "Outside workflow"
    assert record.operation == "startup"
    assert "workflow_id" not in record.__dict__
    assert "run_id" not in record.__dict__


def test_sdk_workflow_logger_preserves_exception_details(sdk_logger, workflow_context, caplog):
    workflow_context(replaying=False)

    try:
        raise ValueError("operation failed")
    except ValueError:
        sdk_logger.exception("Workflow operation failed")

    (record,) = caplog.records
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], ValueError)
    assert record.workflow_id == "task-123"
    assert record.run_id == "run-456"
