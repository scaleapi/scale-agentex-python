# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type
from agentex.types import (
    Agent,
    AgentRpcResponse,
    AgentListResponse,
)
from agentex.types.shared import DeleteResponse

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestAgents:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_retrieve(self, client: Agentex) -> None:
        agent = client.agents.retrieve(
            "agent_id",
        )
        assert_matches_type(Agent, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_retrieve(self, client: Agentex) -> None:
        response = client.agents.with_raw_response.retrieve(
            "agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = response.parse()
        assert_matches_type(Agent, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_retrieve(self, client: Agentex) -> None:
        with client.agents.with_streaming_response.retrieve(
            "agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = response.parse()
            assert_matches_type(Agent, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_retrieve(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_list(self, client: Agentex) -> None:
        agent = client.agents.list()
        assert_matches_type(AgentListResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_list_with_all_params(self, client: Agentex) -> None:
        agent = client.agents.list(
            task_id="task_id",
        )
        assert_matches_type(AgentListResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_list(self, client: Agentex) -> None:
        response = client.agents.with_raw_response.list()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = response.parse()
        assert_matches_type(AgentListResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_list(self, client: Agentex) -> None:
        with client.agents.with_streaming_response.list() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = response.parse()
            assert_matches_type(AgentListResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_delete(self, client: Agentex) -> None:
        agent = client.agents.delete(
            "agent_id",
        )
        assert_matches_type(DeleteResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_delete(self, client: Agentex) -> None:
        response = client.agents.with_raw_response.delete(
            "agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = response.parse()
        assert_matches_type(DeleteResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_delete(self, client: Agentex) -> None:
        with client.agents.with_streaming_response.delete(
            "agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = response.parse()
            assert_matches_type(DeleteResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_delete(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.with_raw_response.delete(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_delete_by_name(self, client: Agentex) -> None:
        agent = client.agents.delete_by_name(
            "agent_name",
        )
        assert_matches_type(DeleteResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_delete_by_name(self, client: Agentex) -> None:
        response = client.agents.with_raw_response.delete_by_name(
            "agent_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = response.parse()
        assert_matches_type(DeleteResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_delete_by_name(self, client: Agentex) -> None:
        with client.agents.with_streaming_response.delete_by_name(
            "agent_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = response.parse()
            assert_matches_type(DeleteResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_delete_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            client.agents.with_raw_response.delete_by_name(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_retrieve_by_name(self, client: Agentex) -> None:
        agent = client.agents.retrieve_by_name(
            "agent_name",
        )
        assert_matches_type(Agent, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_retrieve_by_name(self, client: Agentex) -> None:
        response = client.agents.with_raw_response.retrieve_by_name(
            "agent_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = response.parse()
        assert_matches_type(Agent, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_retrieve_by_name(self, client: Agentex) -> None:
        with client.agents.with_streaming_response.retrieve_by_name(
            "agent_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = response.parse()
            assert_matches_type(Agent, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_retrieve_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            client.agents.with_raw_response.retrieve_by_name(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_rpc(self, client: Agentex) -> None:
        agent = client.agents.rpc(
            agent_id="agent_id",
            method="event/send",
            params={},
        )
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_rpc_with_all_params(self, client: Agentex) -> None:
        agent = client.agents.rpc(
            agent_id="agent_id",
            method="event/send",
            params={
                "name": "name",
                "params": {"foo": "bar"},
            },
            id=0,
            jsonrpc="2.0",
        )
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_rpc(self, client: Agentex) -> None:
        response = client.agents.with_raw_response.rpc(
            agent_id="agent_id",
            method="event/send",
            params={},
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = response.parse()
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_rpc(self, client: Agentex) -> None:
        with client.agents.with_streaming_response.rpc(
            agent_id="agent_id",
            method="event/send",
            params={},
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = response.parse()
            assert_matches_type(AgentRpcResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_rpc(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.with_raw_response.rpc(
                agent_id="",
                method="event/send",
                params={},
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_rpc_by_name(self, client: Agentex) -> None:
        agent = client.agents.rpc_by_name(
            agent_name="agent_name",
            method="event/send",
            params={},
        )
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_rpc_by_name_with_all_params(self, client: Agentex) -> None:
        agent = client.agents.rpc_by_name(
            agent_name="agent_name",
            method="event/send",
            params={
                "name": "name",
                "params": {"foo": "bar"},
            },
            id=0,
            jsonrpc="2.0",
        )
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_rpc_by_name(self, client: Agentex) -> None:
        response = client.agents.with_raw_response.rpc_by_name(
            agent_name="agent_name",
            method="event/send",
            params={},
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = response.parse()
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_rpc_by_name(self, client: Agentex) -> None:
        with client.agents.with_streaming_response.rpc_by_name(
            agent_name="agent_name",
            method="event/send",
            params={},
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = response.parse()
            assert_matches_type(AgentRpcResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_rpc_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            client.agents.with_raw_response.rpc_by_name(
                agent_name="",
                method="event/send",
                params={},
            )


class TestAsyncAgents:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_retrieve(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.retrieve(
            "agent_id",
        )
        assert_matches_type(Agent, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.with_raw_response.retrieve(
            "agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = await response.parse()
        assert_matches_type(Agent, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.with_streaming_response.retrieve(
            "agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = await response.parse()
            assert_matches_type(Agent, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_retrieve(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_list(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.list()
        assert_matches_type(AgentListResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_list_with_all_params(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.list(
            task_id="task_id",
        )
        assert_matches_type(AgentListResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_list(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.with_raw_response.list()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = await response.parse()
        assert_matches_type(AgentListResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_list(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.with_streaming_response.list() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = await response.parse()
            assert_matches_type(AgentListResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_delete(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.delete(
            "agent_id",
        )
        assert_matches_type(DeleteResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_delete(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.with_raw_response.delete(
            "agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = await response.parse()
        assert_matches_type(DeleteResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_delete(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.with_streaming_response.delete(
            "agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = await response.parse()
            assert_matches_type(DeleteResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_delete(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.with_raw_response.delete(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_delete_by_name(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.delete_by_name(
            "agent_name",
        )
        assert_matches_type(DeleteResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_delete_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.with_raw_response.delete_by_name(
            "agent_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = await response.parse()
        assert_matches_type(DeleteResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_delete_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.with_streaming_response.delete_by_name(
            "agent_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = await response.parse()
            assert_matches_type(DeleteResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_delete_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            await async_client.agents.with_raw_response.delete_by_name(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.retrieve_by_name(
            "agent_name",
        )
        assert_matches_type(Agent, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.with_raw_response.retrieve_by_name(
            "agent_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = await response.parse()
        assert_matches_type(Agent, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.with_streaming_response.retrieve_by_name(
            "agent_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = await response.parse()
            assert_matches_type(Agent, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            await async_client.agents.with_raw_response.retrieve_by_name(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_rpc(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.rpc(
            agent_id="agent_id",
            method="event/send",
            params={},
        )
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_rpc_with_all_params(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.rpc(
            agent_id="agent_id",
            method="event/send",
            params={
                "name": "name",
                "params": {"foo": "bar"},
            },
            id=0,
            jsonrpc="2.0",
        )
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_rpc(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.with_raw_response.rpc(
            agent_id="agent_id",
            method="event/send",
            params={},
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = await response.parse()
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_rpc(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.with_streaming_response.rpc(
            agent_id="agent_id",
            method="event/send",
            params={},
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = await response.parse()
            assert_matches_type(AgentRpcResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_rpc(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.with_raw_response.rpc(
                agent_id="",
                method="event/send",
                params={},
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_rpc_by_name(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.rpc_by_name(
            agent_name="agent_name",
            method="event/send",
            params={},
        )
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_rpc_by_name_with_all_params(self, async_client: AsyncAgentex) -> None:
        agent = await async_client.agents.rpc_by_name(
            agent_name="agent_name",
            method="event/send",
            params={
                "name": "name",
                "params": {"foo": "bar"},
            },
            id=0,
            jsonrpc="2.0",
        )
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_rpc_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.with_raw_response.rpc_by_name(
            agent_name="agent_name",
            method="event/send",
            params={},
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        agent = await response.parse()
        assert_matches_type(AgentRpcResponse, agent, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_rpc_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.with_streaming_response.rpc_by_name(
            agent_name="agent_name",
            method="event/send",
            params={},
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            agent = await response.parse()
            assert_matches_type(AgentRpcResponse, agent, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_rpc_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_name` but received ''"):
            await async_client.agents.with_raw_response.rpc_by_name(
                agent_name="",
                method="event/send",
                params={},
            )
