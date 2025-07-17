# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import TypeAlias

from .event import Event

__all__ = ["EventListResponse"]

EventListResponse: TypeAlias = List[Event]
