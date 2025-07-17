# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["Span"]


class Span(BaseModel):
    id: str

    name: str
    """Name that describes what operation this span represents"""

    start_time: datetime
    """The time the span started"""

    trace_id: str
    """Unique identifier for the trace this span belongs to"""

    data: Union[Dict[str, object], List[Dict[str, object]], None] = None
    """Any additional metadata or context for the span"""

    end_time: Optional[datetime] = None
    """The time the span ended"""

    input: Union[Dict[str, object], List[Dict[str, object]], None] = None
    """Input parameters or data for the operation"""

    output: Union[Dict[str, object], List[Dict[str, object]], None] = None
    """Output data resulting from the operation"""

    parent_id: Optional[str] = None
    """ID of the parent span if this is a child span in a trace"""
