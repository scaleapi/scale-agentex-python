# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["WebhookCreateWebhookTriggerParams"]


class WebhookCreateWebhookTriggerParams(TypedDict, total=False):
    agent_name: Required[str]
    """The agent the webhook drives."""

    forward_path: Required[str]
    """Subpath the agent's own route handles, e.g.

    'github-pr/<config-id>'. Appended to /agents/forward/name/{agent_name}/ to form
    the webhook URL.
    """

    name: Required[str]
    """
    Signature-lookup key: the repo full_name (github) or api_app_id (slack) that the
    forward ingress matches the incoming webhook against.
    """

    base_url: Optional[str]
    """
    Optional public agentex base URL for the returned webhook_url; defaults to the
    AGENTEX_PUBLIC_URL env var.
    """

    secret: Optional[str]
    """Signing secret.

    For GitHub, omit to generate one, or provide an existing webhook secret. For
    Slack, this is required and must be the Slack app's Signing Secret.
    """

    source: Literal["internal", "external", "github", "slack"]
    """Webhook source whose signature is verified (github or slack)."""
