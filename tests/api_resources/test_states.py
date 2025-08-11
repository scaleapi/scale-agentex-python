# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type
from agentex.types import State, StateListResponse

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestStates:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_create(self, client: Agentex) -> None:
        state = client.states.create(
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        )
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_create(self, client: Agentex) -> None:
        response = client.states.with_raw_response.create(
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = response.parse()
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_create(self, client: Agentex) -> None:
        with client.states.with_streaming_response.create(
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = response.parse()
            assert_matches_type(State, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_retrieve(self, client: Agentex) -> None:
        state = client.states.retrieve(
            "state_id",
        )
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_retrieve(self, client: Agentex) -> None:
        response = client.states.with_raw_response.retrieve(
            "state_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = response.parse()
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_retrieve(self, client: Agentex) -> None:
        with client.states.with_streaming_response.retrieve(
            "state_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = response.parse()
            assert_matches_type(State, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_retrieve(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `state_id` but received ''"):
            client.states.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_update(self, client: Agentex) -> None:
        state = client.states.update(
            state_id="state_id",
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        )
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_update(self, client: Agentex) -> None:
        response = client.states.with_raw_response.update(
            state_id="state_id",
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = response.parse()
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_update(self, client: Agentex) -> None:
        with client.states.with_streaming_response.update(
            state_id="state_id",
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = response.parse()
            assert_matches_type(State, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_update(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `state_id` but received ''"):
            client.states.with_raw_response.update(
                state_id="",
                agent_id="agent_id",
                state={"foo": "bar"},
                task_id="task_id",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_list(self, client: Agentex) -> None:
        state = client.states.list()
        assert_matches_type(StateListResponse, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_list_with_all_params(self, client: Agentex) -> None:
        state = client.states.list(
            agent_id="agent_id",
            task_id="task_id",
        )
        assert_matches_type(StateListResponse, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_list(self, client: Agentex) -> None:
        response = client.states.with_raw_response.list()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = response.parse()
        assert_matches_type(StateListResponse, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_list(self, client: Agentex) -> None:
        with client.states.with_streaming_response.list() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = response.parse()
            assert_matches_type(StateListResponse, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_delete(self, client: Agentex) -> None:
        state = client.states.delete(
            "state_id",
        )
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_delete(self, client: Agentex) -> None:
        response = client.states.with_raw_response.delete(
            "state_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = response.parse()
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_delete(self, client: Agentex) -> None:
        with client.states.with_streaming_response.delete(
            "state_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = response.parse()
            assert_matches_type(State, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_delete(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `state_id` but received ''"):
            client.states.with_raw_response.delete(
                "",
            )


class TestAsyncStates:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_create(self, async_client: AsyncAgentex) -> None:
        state = await async_client.states.create(
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        )
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_create(self, async_client: AsyncAgentex) -> None:
        response = await async_client.states.with_raw_response.create(
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = await response.parse()
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_create(self, async_client: AsyncAgentex) -> None:
        async with async_client.states.with_streaming_response.create(
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = await response.parse()
            assert_matches_type(State, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_retrieve(self, async_client: AsyncAgentex) -> None:
        state = await async_client.states.retrieve(
            "state_id",
        )
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentex) -> None:
        response = await async_client.states.with_raw_response.retrieve(
            "state_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = await response.parse()
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve(self, async_client: AsyncAgentex) -> None:
        async with async_client.states.with_streaming_response.retrieve(
            "state_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = await response.parse()
            assert_matches_type(State, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_retrieve(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `state_id` but received ''"):
            await async_client.states.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_update(self, async_client: AsyncAgentex) -> None:
        state = await async_client.states.update(
            state_id="state_id",
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        )
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_update(self, async_client: AsyncAgentex) -> None:
        response = await async_client.states.with_raw_response.update(
            state_id="state_id",
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = await response.parse()
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_update(self, async_client: AsyncAgentex) -> None:
        async with async_client.states.with_streaming_response.update(
            state_id="state_id",
            agent_id="agent_id",
            state={"foo": "bar"},
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = await response.parse()
            assert_matches_type(State, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_update(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `state_id` but received ''"):
            await async_client.states.with_raw_response.update(
                state_id="",
                agent_id="agent_id",
                state={"foo": "bar"},
                task_id="task_id",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_list(self, async_client: AsyncAgentex) -> None:
        state = await async_client.states.list()
        assert_matches_type(StateListResponse, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_list_with_all_params(self, async_client: AsyncAgentex) -> None:
        state = await async_client.states.list(
            agent_id="agent_id",
            task_id="task_id",
        )
        assert_matches_type(StateListResponse, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_list(self, async_client: AsyncAgentex) -> None:
        response = await async_client.states.with_raw_response.list()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = await response.parse()
        assert_matches_type(StateListResponse, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_list(self, async_client: AsyncAgentex) -> None:
        async with async_client.states.with_streaming_response.list() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = await response.parse()
            assert_matches_type(StateListResponse, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_delete(self, async_client: AsyncAgentex) -> None:
        state = await async_client.states.delete(
            "state_id",
        )
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_delete(self, async_client: AsyncAgentex) -> None:
        response = await async_client.states.with_raw_response.delete(
            "state_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        state = await response.parse()
        assert_matches_type(State, state, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_delete(self, async_client: AsyncAgentex) -> None:
        async with async_client.states.with_streaming_response.delete(
            "state_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            state = await response.parse()
            assert_matches_type(State, state, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_delete(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `state_id` but received ''"):
            await async_client.states.with_raw_response.delete(
                "",
            )
