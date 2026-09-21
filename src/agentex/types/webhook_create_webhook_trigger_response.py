# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["WebhookCreateWebhookTriggerResponse"]


class WebhookCreateWebhookTriggerResponse(BaseModel):
    agent_name: str
    """The agent the webhook drives."""

    key_id: str
    """The created agent API key id."""

    name: str
    """Signature-lookup key (repo full_name / api_app_id)."""

    secret: str
    """The signing secret — shown once; paste into the source's webhook config."""

    source: Literal["internal", "external", "github", "slack"]
    """Webhook source (github or slack)."""

    webhook_path: str
    """The forward path to POST webhooks to."""

    webhook_url: Optional[str] = None
    """Full webhook URL to paste into the source (None if no base URL configured)."""
