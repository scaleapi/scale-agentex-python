# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type
from agentex.types import WebhookCreateWebhookTriggerResponse

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestWebhooks:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_create_webhook_trigger(self, client: Agentex) -> None:
        webhook = client.webhooks.create_webhook_trigger(
            agent_name="agent_name",
            forward_path="forward_path",
            name="name",
        )
        assert_matches_type(WebhookCreateWebhookTriggerResponse, webhook, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_create_webhook_trigger_with_all_params(self, client: Agentex) -> None:
        webhook = client.webhooks.create_webhook_trigger(
            agent_name="agent_name",
            forward_path="forward_path",
            name="name",
            base_url="base_url",
            secret="secret",
            source="internal",
        )
        assert_matches_type(WebhookCreateWebhookTriggerResponse, webhook, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_create_webhook_trigger(self, client: Agentex) -> None:
        response = client.webhooks.with_raw_response.create_webhook_trigger(
            agent_name="agent_name",
            forward_path="forward_path",
            name="name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        webhook = response.parse()
        assert_matches_type(WebhookCreateWebhookTriggerResponse, webhook, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_create_webhook_trigger(self, client: Agentex) -> None:
        with client.webhooks.with_streaming_response.create_webhook_trigger(
            agent_name="agent_name",
            forward_path="forward_path",
            name="name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            webhook = response.parse()
            assert_matches_type(WebhookCreateWebhookTriggerResponse, webhook, path=["response"])

        assert cast(Any, response.is_closed) is True


class TestAsyncWebhooks:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_create_webhook_trigger(self, async_client: AsyncAgentex) -> None:
        webhook = await async_client.webhooks.create_webhook_trigger(
            agent_name="agent_name",
            forward_path="forward_path",
            name="name",
        )
        assert_matches_type(WebhookCreateWebhookTriggerResponse, webhook, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_create_webhook_trigger_with_all_params(self, async_client: AsyncAgentex) -> None:
        webhook = await async_client.webhooks.create_webhook_trigger(
            agent_name="agent_name",
            forward_path="forward_path",
            name="name",
            base_url="base_url",
            secret="secret",
            source="internal",
        )
        assert_matches_type(WebhookCreateWebhookTriggerResponse, webhook, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_create_webhook_trigger(self, async_client: AsyncAgentex) -> None:
        response = await async_client.webhooks.with_raw_response.create_webhook_trigger(
            agent_name="agent_name",
            forward_path="forward_path",
            name="name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        webhook = await response.parse()
        assert_matches_type(WebhookCreateWebhookTriggerResponse, webhook, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_create_webhook_trigger(self, async_client: AsyncAgentex) -> None:
        async with async_client.webhooks.with_streaming_response.create_webhook_trigger(
            agent_name="agent_name",
            forward_path="forward_path",
            name="name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            webhook = await response.parse()
            assert_matches_type(WebhookCreateWebhookTriggerResponse, webhook, path=["response"])

        assert cast(Any, response.is_closed) is True
