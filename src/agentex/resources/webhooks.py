# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal

import httpx

from ..types import webhook_create_webhook_trigger_params
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from .._utils import maybe_transform, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._base_client import make_request_options
from ..types.webhook_create_webhook_trigger_response import WebhookCreateWebhookTriggerResponse

__all__ = ["WebhooksResource", "AsyncWebhooksResource"]


class WebhooksResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> WebhooksResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return WebhooksResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> WebhooksResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return WebhooksResourceWithStreamingResponse(self)

    def create_webhook_trigger(
        self,
        *,
        agent_name: str,
        forward_path: str,
        name: str,
        base_url: Optional[str] | Omit = omit,
        secret: Optional[str] | Omit = omit,
        source: Literal["internal", "external", "github", "slack"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> WebhookCreateWebhookTriggerResponse:
        """
        Wire a webhook trigger in one call.

        Registers the source's signature-verification key (github/slack) for the agent
        and returns the ready-to-paste forward webhook URL plus the signing secret
        (shown once). The webhook then flows through the existing /agents/forward
        ingress, which verifies the signature against this key. Bundles the existing
        key-create + URL composition so a UI (or a curl) can set up a trigger without
        two steps.

        Args:
          agent_name: The agent the webhook drives.

          forward_path: Subpath the agent's own route handles, e.g. 'github-pr/<config-id>'. Appended to
              /agents/forward/name/{agent_name}/ to form the webhook URL.

          name: Signature-lookup key: the repo full_name (github) or api_app_id (slack) that the
              forward ingress matches the incoming webhook against.

          base_url: Optional public agentex base URL for the returned webhook_url; defaults to the
              AGENTEX_PUBLIC_URL env var.

          secret: Signing secret. For GitHub, omit to generate one, or provide an existing webhook
              secret. For Slack, this is required and must be the Slack app's Signing Secret.

          source: Webhook source whose signature is verified (github or slack).

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agent_api_keys/webhook-trigger",
            body=maybe_transform(
                {
                    "agent_name": agent_name,
                    "forward_path": forward_path,
                    "name": name,
                    "base_url": base_url,
                    "secret": secret,
                    "source": source,
                },
                webhook_create_webhook_trigger_params.WebhookCreateWebhookTriggerParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=WebhookCreateWebhookTriggerResponse,
        )


class AsyncWebhooksResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncWebhooksResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncWebhooksResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncWebhooksResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return AsyncWebhooksResourceWithStreamingResponse(self)

    async def create_webhook_trigger(
        self,
        *,
        agent_name: str,
        forward_path: str,
        name: str,
        base_url: Optional[str] | Omit = omit,
        secret: Optional[str] | Omit = omit,
        source: Literal["internal", "external", "github", "slack"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> WebhookCreateWebhookTriggerResponse:
        """
        Wire a webhook trigger in one call.

        Registers the source's signature-verification key (github/slack) for the agent
        and returns the ready-to-paste forward webhook URL plus the signing secret
        (shown once). The webhook then flows through the existing /agents/forward
        ingress, which verifies the signature against this key. Bundles the existing
        key-create + URL composition so a UI (or a curl) can set up a trigger without
        two steps.

        Args:
          agent_name: The agent the webhook drives.

          forward_path: Subpath the agent's own route handles, e.g. 'github-pr/<config-id>'. Appended to
              /agents/forward/name/{agent_name}/ to form the webhook URL.

          name: Signature-lookup key: the repo full_name (github) or api_app_id (slack) that the
              forward ingress matches the incoming webhook against.

          base_url: Optional public agentex base URL for the returned webhook_url; defaults to the
              AGENTEX_PUBLIC_URL env var.

          secret: Signing secret. For GitHub, omit to generate one, or provide an existing webhook
              secret. For Slack, this is required and must be the Slack app's Signing Secret.

          source: Webhook source whose signature is verified (github or slack).

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agent_api_keys/webhook-trigger",
            body=await async_maybe_transform(
                {
                    "agent_name": agent_name,
                    "forward_path": forward_path,
                    "name": name,
                    "base_url": base_url,
                    "secret": secret,
                    "source": source,
                },
                webhook_create_webhook_trigger_params.WebhookCreateWebhookTriggerParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=WebhookCreateWebhookTriggerResponse,
        )


class WebhooksResourceWithRawResponse:
    def __init__(self, webhooks: WebhooksResource) -> None:
        self._webhooks = webhooks

        self.create_webhook_trigger = to_raw_response_wrapper(
            webhooks.create_webhook_trigger,
        )


class AsyncWebhooksResourceWithRawResponse:
    def __init__(self, webhooks: AsyncWebhooksResource) -> None:
        self._webhooks = webhooks

        self.create_webhook_trigger = async_to_raw_response_wrapper(
            webhooks.create_webhook_trigger,
        )


class WebhooksResourceWithStreamingResponse:
    def __init__(self, webhooks: WebhooksResource) -> None:
        self._webhooks = webhooks

        self.create_webhook_trigger = to_streamed_response_wrapper(
            webhooks.create_webhook_trigger,
        )


class AsyncWebhooksResourceWithStreamingResponse:
    def __init__(self, webhooks: AsyncWebhooksResource) -> None:
        self._webhooks = webhooks

        self.create_webhook_trigger = async_to_streamed_response_wrapper(
            webhooks.create_webhook_trigger,
        )
