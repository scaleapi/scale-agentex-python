# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type
from agentex.types import AgentRpcResponse
from agentex.types.agents import (
    DeploymentListResponse,
    DeploymentCreateResponse,
    DeploymentPromoteResponse,
    DeploymentRetrieveResponse,
)
from agentex.types.shared import DeleteResponse

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestDeployments:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_create(self, client: Agentex) -> None:
        deployment = client.agents.deployments.create(
            agent_id="agent_id",
            docker_image="docker_image",
        )
        assert_matches_type(DeploymentCreateResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_create_with_all_params(self, client: Agentex) -> None:
        deployment = client.agents.deployments.create(
            agent_id="agent_id",
            docker_image="docker_image",
            helm_release_name="helm_release_name",
            registration_metadata={"foo": "bar"},
            sgp_deploy_id="sgp_deploy_id",
        )
        assert_matches_type(DeploymentCreateResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_create(self, client: Agentex) -> None:
        response = client.agents.deployments.with_raw_response.create(
            agent_id="agent_id",
            docker_image="docker_image",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = response.parse()
        assert_matches_type(DeploymentCreateResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_create(self, client: Agentex) -> None:
        with client.agents.deployments.with_streaming_response.create(
            agent_id="agent_id",
            docker_image="docker_image",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = response.parse()
            assert_matches_type(DeploymentCreateResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_create(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.deployments.with_raw_response.create(
                agent_id="",
                docker_image="docker_image",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_retrieve(self, client: Agentex) -> None:
        deployment = client.agents.deployments.retrieve(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )
        assert_matches_type(DeploymentRetrieveResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_retrieve(self, client: Agentex) -> None:
        response = client.agents.deployments.with_raw_response.retrieve(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = response.parse()
        assert_matches_type(DeploymentRetrieveResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_retrieve(self, client: Agentex) -> None:
        with client.agents.deployments.with_streaming_response.retrieve(
            deployment_id="deployment_id",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = response.parse()
            assert_matches_type(DeploymentRetrieveResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_retrieve(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.deployments.with_raw_response.retrieve(
                deployment_id="deployment_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `deployment_id` but received ''"):
            client.agents.deployments.with_raw_response.retrieve(
                deployment_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_list(self, client: Agentex) -> None:
        deployment = client.agents.deployments.list(
            agent_id="agent_id",
        )
        assert_matches_type(DeploymentListResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_list_with_all_params(self, client: Agentex) -> None:
        deployment = client.agents.deployments.list(
            agent_id="agent_id",
            limit=1,
            order_by="order_by",
            order_direction="order_direction",
            page_number=1,
        )
        assert_matches_type(DeploymentListResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_list(self, client: Agentex) -> None:
        response = client.agents.deployments.with_raw_response.list(
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = response.parse()
        assert_matches_type(DeploymentListResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_list(self, client: Agentex) -> None:
        with client.agents.deployments.with_streaming_response.list(
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = response.parse()
            assert_matches_type(DeploymentListResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_list(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.deployments.with_raw_response.list(
                agent_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_delete(self, client: Agentex) -> None:
        deployment = client.agents.deployments.delete(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )
        assert_matches_type(DeleteResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_delete(self, client: Agentex) -> None:
        response = client.agents.deployments.with_raw_response.delete(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = response.parse()
        assert_matches_type(DeleteResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_delete(self, client: Agentex) -> None:
        with client.agents.deployments.with_streaming_response.delete(
            deployment_id="deployment_id",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = response.parse()
            assert_matches_type(DeleteResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_delete(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.deployments.with_raw_response.delete(
                deployment_id="deployment_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `deployment_id` but received ''"):
            client.agents.deployments.with_raw_response.delete(
                deployment_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_preview_rpc(self, client: Agentex) -> None:
        deployment = client.agents.deployments.preview_rpc(
            deployment_id="deployment_id",
            agent_id="agent_id",
            method="event/send",
            params={},
        )
        assert_matches_type(AgentRpcResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_preview_rpc_with_all_params(self, client: Agentex) -> None:
        deployment = client.agents.deployments.preview_rpc(
            deployment_id="deployment_id",
            agent_id="agent_id",
            method="event/send",
            params={
                "name": "name",
                "params": {"foo": "bar"},
                "task_metadata": {"foo": "bar"},
            },
            id=0,
            jsonrpc="2.0",
        )
        assert_matches_type(AgentRpcResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_preview_rpc(self, client: Agentex) -> None:
        response = client.agents.deployments.with_raw_response.preview_rpc(
            deployment_id="deployment_id",
            agent_id="agent_id",
            method="event/send",
            params={},
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = response.parse()
        assert_matches_type(AgentRpcResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_preview_rpc(self, client: Agentex) -> None:
        with client.agents.deployments.with_streaming_response.preview_rpc(
            deployment_id="deployment_id",
            agent_id="agent_id",
            method="event/send",
            params={},
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = response.parse()
            assert_matches_type(AgentRpcResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_preview_rpc(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.deployments.with_raw_response.preview_rpc(
                deployment_id="deployment_id",
                agent_id="",
                method="event/send",
                params={},
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `deployment_id` but received ''"):
            client.agents.deployments.with_raw_response.preview_rpc(
                deployment_id="",
                agent_id="agent_id",
                method="event/send",
                params={},
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_promote(self, client: Agentex) -> None:
        deployment = client.agents.deployments.promote(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )
        assert_matches_type(DeploymentPromoteResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_promote(self, client: Agentex) -> None:
        response = client.agents.deployments.with_raw_response.promote(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = response.parse()
        assert_matches_type(DeploymentPromoteResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_promote(self, client: Agentex) -> None:
        with client.agents.deployments.with_streaming_response.promote(
            deployment_id="deployment_id",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = response.parse()
            assert_matches_type(DeploymentPromoteResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_promote(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.deployments.with_raw_response.promote(
                deployment_id="deployment_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `deployment_id` but received ''"):
            client.agents.deployments.with_raw_response.promote(
                deployment_id="",
                agent_id="agent_id",
            )


class TestAsyncDeployments:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_create(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.create(
            agent_id="agent_id",
            docker_image="docker_image",
        )
        assert_matches_type(DeploymentCreateResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_create_with_all_params(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.create(
            agent_id="agent_id",
            docker_image="docker_image",
            helm_release_name="helm_release_name",
            registration_metadata={"foo": "bar"},
            sgp_deploy_id="sgp_deploy_id",
        )
        assert_matches_type(DeploymentCreateResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_create(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.deployments.with_raw_response.create(
            agent_id="agent_id",
            docker_image="docker_image",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = await response.parse()
        assert_matches_type(DeploymentCreateResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_create(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.deployments.with_streaming_response.create(
            agent_id="agent_id",
            docker_image="docker_image",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = await response.parse()
            assert_matches_type(DeploymentCreateResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_create(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.create(
                agent_id="",
                docker_image="docker_image",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_retrieve(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.retrieve(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )
        assert_matches_type(DeploymentRetrieveResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.deployments.with_raw_response.retrieve(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = await response.parse()
        assert_matches_type(DeploymentRetrieveResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.deployments.with_streaming_response.retrieve(
            deployment_id="deployment_id",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = await response.parse()
            assert_matches_type(DeploymentRetrieveResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_retrieve(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.retrieve(
                deployment_id="deployment_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `deployment_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.retrieve(
                deployment_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_list(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.list(
            agent_id="agent_id",
        )
        assert_matches_type(DeploymentListResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_list_with_all_params(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.list(
            agent_id="agent_id",
            limit=1,
            order_by="order_by",
            order_direction="order_direction",
            page_number=1,
        )
        assert_matches_type(DeploymentListResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_list(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.deployments.with_raw_response.list(
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = await response.parse()
        assert_matches_type(DeploymentListResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_list(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.deployments.with_streaming_response.list(
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = await response.parse()
            assert_matches_type(DeploymentListResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_list(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.list(
                agent_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_delete(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.delete(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )
        assert_matches_type(DeleteResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_delete(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.deployments.with_raw_response.delete(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = await response.parse()
        assert_matches_type(DeleteResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_delete(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.deployments.with_streaming_response.delete(
            deployment_id="deployment_id",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = await response.parse()
            assert_matches_type(DeleteResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_delete(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.delete(
                deployment_id="deployment_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `deployment_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.delete(
                deployment_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_preview_rpc(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.preview_rpc(
            deployment_id="deployment_id",
            agent_id="agent_id",
            method="event/send",
            params={},
        )
        assert_matches_type(AgentRpcResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_preview_rpc_with_all_params(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.preview_rpc(
            deployment_id="deployment_id",
            agent_id="agent_id",
            method="event/send",
            params={
                "name": "name",
                "params": {"foo": "bar"},
                "task_metadata": {"foo": "bar"},
            },
            id=0,
            jsonrpc="2.0",
        )
        assert_matches_type(AgentRpcResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_preview_rpc(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.deployments.with_raw_response.preview_rpc(
            deployment_id="deployment_id",
            agent_id="agent_id",
            method="event/send",
            params={},
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = await response.parse()
        assert_matches_type(AgentRpcResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_preview_rpc(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.deployments.with_streaming_response.preview_rpc(
            deployment_id="deployment_id",
            agent_id="agent_id",
            method="event/send",
            params={},
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = await response.parse()
            assert_matches_type(AgentRpcResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_preview_rpc(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.preview_rpc(
                deployment_id="deployment_id",
                agent_id="",
                method="event/send",
                params={},
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `deployment_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.preview_rpc(
                deployment_id="",
                agent_id="agent_id",
                method="event/send",
                params={},
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_promote(self, async_client: AsyncAgentex) -> None:
        deployment = await async_client.agents.deployments.promote(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )
        assert_matches_type(DeploymentPromoteResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_promote(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.deployments.with_raw_response.promote(
            deployment_id="deployment_id",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        deployment = await response.parse()
        assert_matches_type(DeploymentPromoteResponse, deployment, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_promote(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.deployments.with_streaming_response.promote(
            deployment_id="deployment_id",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            deployment = await response.parse()
            assert_matches_type(DeploymentPromoteResponse, deployment, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_promote(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.promote(
                deployment_id="deployment_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `deployment_id` but received ''"):
            await async_client.agents.deployments.with_raw_response.promote(
                deployment_id="",
                agent_id="agent_id",
            )
