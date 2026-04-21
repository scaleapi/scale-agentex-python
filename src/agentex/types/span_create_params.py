# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["SpanCreateParams"]


class SpanCreateParams(TypedDict, total=False):
    name: Required[str]
    """Name that describes what operation this span represents"""

    start_time: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """The time the span started"""

    trace_id: Required[str]
    """Unique identifier for the trace this span belongs to"""

    id: Optional[str]
    """Unique identifier for the span. If not provided, an ID will be generated."""

    data: Union[Dict[str, object], Iterable[Dict[str, object]], None]
    """Any additional metadata or context for the span"""

    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """The time the span ended"""

    input: Union[Dict[str, object], Iterable[Dict[str, object]], None]
    """Input parameters or data for the operation"""

    output: Union[Dict[str, object], Iterable[Dict[str, object]], None]
    """Output data resulting from the operation"""

    parent_id: Optional[str]
    """ID of the parent span if this is a child span in a trace"""
