# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import AgentexSDK, AsyncAgentexSDK
from tests.utils import assert_matches_type
from agentex.types import Task

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestName:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip()
    @parametrize
    def test_method_retrieve(self, client: AgentexSDK) -> None:
        name = client.tasks.name.retrieve(
            "task_name",
        )
        assert_matches_type(Task, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_raw_response_retrieve(self, client: AgentexSDK) -> None:
        response = client.tasks.name.with_raw_response.retrieve(
            "task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = response.parse()
        assert_matches_type(Task, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_streaming_response_retrieve(self, client: AgentexSDK) -> None:
        with client.tasks.name.with_streaming_response.retrieve(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = response.parse()
            assert_matches_type(Task, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    def test_path_params_retrieve(self, client: AgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            client.tasks.name.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip()
    @parametrize
    def test_method_delete(self, client: AgentexSDK) -> None:
        name = client.tasks.name.delete(
            "task_name",
        )
        assert_matches_type(Task, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_raw_response_delete(self, client: AgentexSDK) -> None:
        response = client.tasks.name.with_raw_response.delete(
            "task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = response.parse()
        assert_matches_type(Task, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_streaming_response_delete(self, client: AgentexSDK) -> None:
        with client.tasks.name.with_streaming_response.delete(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = response.parse()
            assert_matches_type(Task, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    def test_path_params_delete(self, client: AgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            client.tasks.name.with_raw_response.delete(
                "",
            )

    @pytest.mark.skip()
    @parametrize
    def test_method_stream_events(self, client: AgentexSDK) -> None:
        name_stream = client.tasks.name.stream_events(
            "task_name",
        )
        name_stream.response.close()

    @pytest.mark.skip()
    @parametrize
    def test_raw_response_stream_events(self, client: AgentexSDK) -> None:
        response = client.tasks.name.with_raw_response.stream_events(
            "task_name",
        )

        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        stream = response.parse()
        stream.close()

    @pytest.mark.skip()
    @parametrize
    def test_streaming_response_stream_events(self, client: AgentexSDK) -> None:
        with client.tasks.name.with_streaming_response.stream_events(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            stream = response.parse()
            stream.close()

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    def test_path_params_stream_events(self, client: AgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            client.tasks.name.with_raw_response.stream_events(
                "",
            )


class TestAsyncName:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip()
    @parametrize
    async def test_method_retrieve(self, async_client: AsyncAgentexSDK) -> None:
        name = await async_client.tasks.name.retrieve(
            "task_name",
        )
        assert_matches_type(Task, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentexSDK) -> None:
        response = await async_client.tasks.name.with_raw_response.retrieve(
            "task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = await response.parse()
        assert_matches_type(Task, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_streaming_response_retrieve(self, async_client: AsyncAgentexSDK) -> None:
        async with async_client.tasks.name.with_streaming_response.retrieve(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = await response.parse()
            assert_matches_type(Task, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    async def test_path_params_retrieve(self, async_client: AsyncAgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            await async_client.tasks.name.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip()
    @parametrize
    async def test_method_delete(self, async_client: AsyncAgentexSDK) -> None:
        name = await async_client.tasks.name.delete(
            "task_name",
        )
        assert_matches_type(Task, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_raw_response_delete(self, async_client: AsyncAgentexSDK) -> None:
        response = await async_client.tasks.name.with_raw_response.delete(
            "task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        name = await response.parse()
        assert_matches_type(Task, name, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_streaming_response_delete(self, async_client: AsyncAgentexSDK) -> None:
        async with async_client.tasks.name.with_streaming_response.delete(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            name = await response.parse()
            assert_matches_type(Task, name, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    async def test_path_params_delete(self, async_client: AsyncAgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            await async_client.tasks.name.with_raw_response.delete(
                "",
            )

    @pytest.mark.skip()
    @parametrize
    async def test_method_stream_events(self, async_client: AsyncAgentexSDK) -> None:
        name_stream = await async_client.tasks.name.stream_events(
            "task_name",
        )
        await name_stream.response.aclose()

    @pytest.mark.skip()
    @parametrize
    async def test_raw_response_stream_events(self, async_client: AsyncAgentexSDK) -> None:
        response = await async_client.tasks.name.with_raw_response.stream_events(
            "task_name",
        )

        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        stream = await response.parse()
        await stream.close()

    @pytest.mark.skip()
    @parametrize
    async def test_streaming_response_stream_events(self, async_client: AsyncAgentexSDK) -> None:
        async with async_client.tasks.name.with_streaming_response.stream_events(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            stream = await response.parse()
            await stream.close()

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip()
    @parametrize
    async def test_path_params_stream_events(self, async_client: AsyncAgentexSDK) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            await async_client.tasks.name.with_raw_response.stream_events(
                "",
            )
