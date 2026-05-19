# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["CheckpointPutResponse"]


class CheckpointPutResponse(BaseModel):
    checkpoint_id: str

    checkpoint_ns: str

    thread_id: str
