from typing import Annotated, Literal

from pydantic import Field

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


class AgentexTracingProcessorConfig(BaseModel):
    type: Literal["agentex"] = "agentex"


class SGPTracingProcessorConfig(BaseModel):
    type: Literal["sgp"] = "sgp"
    sgp_api_key: str
    sgp_account_id: str


TracingProcessorConfig = Annotated[
    AgentexTracingProcessorConfig | SGPTracingProcessorConfig,
    Field(discriminator="type"),
]
