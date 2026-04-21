# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["SpanUpdateParams"]


class SpanUpdateParams(TypedDict, total=False):
    data: Union[Dict[str, object], Iterable[Dict[str, object]], None]
    """Any additional metadata or context for the span"""

    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """The time the span ended"""

    input: Union[Dict[str, object], Iterable[Dict[str, object]], None]
    """Input parameters or data for the operation"""

    name: Optional[str]
    """Name that describes what operation this span represents"""

    output: Union[Dict[str, object], Iterable[Dict[str, object]], None]
    """Output data resulting from the operation"""

    parent_id: Optional[str]
    """ID of the parent span if this is a child span in a trace"""

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """The time the span started"""

    trace_id: Optional[str]
    """Unique identifier for the trace this span belongs to"""
