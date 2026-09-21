"""Unit tests for BaseWorkflow's continue-as-new lifecycle helpers.

These exercise the pure decision helpers (``should_continue_as_new`` and
``is_continued_run``) by faking ``workflow.info()`` so we don't need a running
Temporal server. The drain + ``workflow.continue_as_new`` mechanics in
``drain_and_continue_as_new`` / ``run_until_complete`` are best covered by a
replay/integration test against a Temporal test environment (a follow-up).
"""

from __future__ import annotations

from typing import override

import pytest

from agentex.lib.core.temporal.workflows import workflow as base_workflow_module
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow


class _ConcreteWorkflow(BaseWorkflow):
    """Minimal concrete subclass so we can instantiate the ABC in a test."""

    def __init__(self) -> None:
        self.display_name = "test"

    @override
    async def on_task_event_send(self, params) -> None:  # pragma: no cover - unused
        raise NotImplementedError

    @override
    async def on_task_create(self, params) -> None:  # pragma: no cover - unused
        raise NotImplementedError


class _FakeInfo:
    def __init__(self, *, suggested: bool, continued_run_id: str | None = None) -> None:
        self._suggested = suggested
        self.continued_run_id = continued_run_id

    def is_continue_as_new_suggested(self) -> bool:
        return self._suggested


@pytest.fixture
def patch_info(monkeypatch):
    """Patch ``workflow.info`` used inside the BaseWorkflow module."""

    def _apply(*, suggested: bool = False, continued_run_id: str | None = None) -> None:
        monkeypatch.setattr(
            base_workflow_module.workflow,
            "info",
            lambda: _FakeInfo(suggested=suggested, continued_run_id=continued_run_id),
        )

    return _apply


def test_recycles_when_temporal_suggests(patch_info):
    patch_info(suggested=True)
    assert _ConcreteWorkflow().should_continue_as_new() is True


def test_no_recycle_when_not_suggested(patch_info):
    patch_info(suggested=False)
    assert _ConcreteWorkflow().should_continue_as_new() is False


def test_is_continued_run_false_on_original_run(patch_info):
    patch_info(continued_run_id=None)
    assert _ConcreteWorkflow().is_continued_run() is False


def test_is_continued_run_true_after_recycle(patch_info):
    patch_info(continued_run_id="run-123")
    assert _ConcreteWorkflow().is_continued_run() is True
