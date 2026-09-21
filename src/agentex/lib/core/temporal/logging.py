from __future__ import annotations

from typing import Any, override
from collections.abc import MutableMapping

from temporalio import workflow

from agentex.lib.utils.logging import make_logger


class WorkflowLoggerAdapter(workflow.LoggerAdapter):
    """Skip workflow replay logs and add IDs without changing non-workflow logs."""

    @override
    def isEnabledFor(self, level: int) -> bool:
        if not workflow.in_workflow():
            return self.logger.isEnabledFor(level)
        return super().isEnabledFor(level)

    @override
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        if workflow.in_workflow():
            info = workflow.info()
            kwargs["extra"] = {
                "workflow_id": info.workflow_id,
                "run_id": info.run_id,
                **(kwargs.get("extra") or {}),
            }
        return msg, kwargs


def make_workflow_logger(name: str) -> WorkflowLoggerAdapter:
    """Create an SDK logger that suppresses replay and adds workflow/run IDs."""
    return WorkflowLoggerAdapter(make_logger(name), {})
