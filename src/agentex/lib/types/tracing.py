from __future__ import annotations

from typing import Any, Literal
from datetime import datetime

from agentex.lib.utils.model_utils import BaseModel


class BaseModelWithTraceParams(BaseModel):
    """
    Base model with trace parameters.

    Attributes:
        trace_id: The trace ID
        parent_span_id: The parent span ID
    """

    trace_id: str | None = None
    parent_span_id: str | None = None


class Span(BaseModel):
    """In-memory span handed to tracing processors. Owned here, not by the generated client."""

    id: str
    name: str
    start_time: datetime
    trace_id: str
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    end_time: datetime | None = None
    input: dict[str, Any] | list[dict[str, Any]] | None = None
    output: dict[str, Any] | list[dict[str, Any]] | None = None
    parent_id: str | None = None
    task_id: str | None = None


class SGPTracingProcessorConfig(BaseModel):
    type: Literal["sgp"] = "sgp"
    sgp_api_key: str
    sgp_account_id: str
    sgp_base_url: str | None = None


TracingProcessorConfig = SGPTracingProcessorConfig
