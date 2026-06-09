from __future__ import annotations

from typing import Literal

from pydantic import Field, BaseModel

CredentialScheme = Literal["api_key", "bearer"]


class Credentials(BaseModel):
    """Resolved outbound credentials for a downstream target."""

    scheme: CredentialScheme = Field(
        ...,
        description="How to attach the credential to an HTTP request",
    )
    value: str = Field(..., description="Secret credential value")
