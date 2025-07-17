# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import AgentexSDK, AsyncAgentexSDK
from tests.utils import assert_matches_type
from agentex.types import Agent

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestName:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip()
    @parametrize
    def test_method_retrieve(self, client: AgentexSDK) -> None:
        name = client.agents.name.retrieve(
            "agent_name",
        )
        assert_matches_type(Agent, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_raw_response_retrieve(self, client: AgentexSDK) -> None:
        response = client.agents.name.with_raw_response.retrieve(
            "agent_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = response.parse()
        assert_matches_type(Agent, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_streaming_response_retrieve(self, client: AgentexSDK) -> None:
        with client.agents.name.with_streaming_response.retrieve(
            "agent_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = response.parse()
            assert_matches_type(Agent, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    def test_path_params_retrieve(self, client: AgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            client.agents.name.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip()
    @parametrize
    def test_method_delete(self, client: AgentexSDK) -> None:
        name = client.agents.name.delete(
            "agent_name",
        )
        assert_matches_type(Agent, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_raw_response_delete(self, client: AgentexSDK) -> None:
        response = client.agents.name.with_raw_response.delete(
            "agent_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = response.parse()
        assert_matches_type(Agent, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_streaming_response_delete(self, client: AgentexSDK) -> None:
        with client.agents.name.with_streaming_response.delete(
            "agent_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = response.parse()
            assert_matches_type(Agent, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    def test_path_params_delete(self, client: AgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            client.agents.name.with_raw_response.delete(
                "",
            )

    @pytest.mark.skip()
    @parametrize
    def test_method_rpc(self, client: AgentexSDK) -> None:
        name = client.agents.name.rpc(
            agent_name="agent_name",
            method="event/send",
            params={},
        )
        assert_matches_type(object, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_method_rpc_with_all_params(self, client: AgentexSDK) -> None:
        name = client.agents.name.rpc(
            agent_name="agent_name",
            method="event/send",
            params={
                "name": "name",
                "params": {"foo": "bar"},
            },
            id=0,
            jsonrpc="2.0",
        )
        assert_matches_type(object, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_raw_response_rpc(self, client: AgentexSDK) -> None:
        response = client.agents.name.with_raw_response.rpc(
            agent_name="agent_name",
            method="event/send",
            params={},
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = response.parse()
        assert_matches_type(object, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_streaming_response_rpc(self, client: AgentexSDK) -> None:
        with client.agents.name.with_streaming_response.rpc(
            agent_name="agent_name",
            method="event/send",
            params={},
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = response.parse()
            assert_matches_type(object, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    def test_path_params_rpc(self, client: AgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            client.agents.name.with_raw_response.rpc(
                agent_name="",
                method="event/send",
                params={},
            )


class TestAsyncName:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip()
    @parametrize
    async def test_method_retrieve(self, async_client: AsyncAgentexSDK) -> None:
        name = await async_client.agents.name.retrieve(
            "agent_name",
        )
        assert_matches_type(Agent, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentexSDK) -> None:
        response = await async_client.agents.name.with_raw_response.retrieve(
            "agent_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = await response.parse()
        assert_matches_type(Agent, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_streaming_response_retrieve(self, async_client: AsyncAgentexSDK) -> None:
        async with async_client.agents.name.with_streaming_response.retrieve(
            "agent_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = await response.parse()
            assert_matches_type(Agent, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    async def test_path_params_retrieve(self, async_client: AsyncAgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            await async_client.agents.name.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip()
    @parametrize
    async def test_method_delete(self, async_client: AsyncAgentexSDK) -> None:
        name = await async_client.agents.name.delete(
            "agent_name",
        )
        assert_matches_type(Agent, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_raw_response_delete(self, async_client: AsyncAgentexSDK) -> None:
        response = await async_client.agents.name.with_raw_response.delete(
            "agent_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = await response.parse()
        assert_matches_type(Agent, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_streaming_response_delete(self, async_client: AsyncAgentexSDK) -> None:
        async with async_client.agents.name.with_streaming_response.delete(
            "agent_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = await response.parse()
            assert_matches_type(Agent, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    async def test_path_params_delete(self, async_client: AsyncAgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            await async_client.agents.name.with_raw_response.delete(
                "",
            )

    @pytest.mark.skip()
    @parametrize
    async def test_method_rpc(self, async_client: AsyncAgentexSDK) -> None:
        name = await async_client.agents.name.rpc(
            agent_name="agent_name",
            method="event/send",
            params={},
        )
        assert_matches_type(object, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_method_rpc_with_all_params(self, async_client: AsyncAgentexSDK) -> None:
        name = await async_client.agents.name.rpc(
            agent_name="agent_name",
            method="event/send",
            params={
                "name": "name",
                "params": {"foo": "bar"},
            },
            id=0,
            jsonrpc="2.0",
        )
        assert_matches_type(object, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_raw_response_rpc(self, async_client: AsyncAgentexSDK) -> None:
        response = await async_client.agents.name.with_raw_response.rpc(
            agent_name="agent_name",
            method="event/send",
            params={},
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = await response.parse()
        assert_matches_type(object, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_streaming_response_rpc(self, async_client: AsyncAgentexSDK) -> None:
        async with async_client.agents.name.with_streaming_response.rpc(
            agent_name="agent_name",
            method="event/send",
            params={},
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = await response.parse()
            assert_matches_type(object, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    async def test_path_params_rpc(self, async_client: AsyncAgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            await async_client.agents.name.with_raw_response.rpc(
                agent_name="",
                method="event/send",
                params={},
            )
