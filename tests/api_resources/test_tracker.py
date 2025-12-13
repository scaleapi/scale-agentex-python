# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type
from agentex.types import AgentTaskTracker, TrackerListResponse

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestTracker:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_retrieve(self, client: Agentex) -> None:
        tracker = client.tracker.retrieve(
            "tracker_id",
        )
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_retrieve(self, client: Agentex) -> None:
        response = client.tracker.with_raw_response.retrieve(
            "tracker_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        tracker = response.parse()
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_retrieve(self, client: Agentex) -> None:
        with client.tracker.with_streaming_response.retrieve(
            "tracker_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            tracker = response.parse()
            assert_matches_type(AgentTaskTracker, tracker, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_retrieve(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `tracker_id` but received ''"):
            client.tracker.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_update(self, client: Agentex) -> None:
        tracker = client.tracker.update(
            tracker_id="tracker_id",
        )
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_update_with_all_params(self, client: Agentex) -> None:
        tracker = client.tracker.update(
            tracker_id="tracker_id",
            last_processed_event_id="last_processed_event_id",
            status="status",
            status_reason="status_reason",
        )
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_update(self, client: Agentex) -> None:
        response = client.tracker.with_raw_response.update(
            tracker_id="tracker_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        tracker = response.parse()
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_update(self, client: Agentex) -> None:
        with client.tracker.with_streaming_response.update(
            tracker_id="tracker_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            tracker = response.parse()
            assert_matches_type(AgentTaskTracker, tracker, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_path_params_update(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `tracker_id` but received ''"):
            client.tracker.with_raw_response.update(
                tracker_id="",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_list(self, client: Agentex) -> None:
        tracker = client.tracker.list()
        assert_matches_type(TrackerListResponse, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_list_with_all_params(self, client: Agentex) -> None:
        tracker = client.tracker.list(
            agent_id="agent_id",
            task_id="task_id",
        )
        assert_matches_type(TrackerListResponse, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_list(self, client: Agentex) -> None:
        response = client.tracker.with_raw_response.list()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        tracker = response.parse()
        assert_matches_type(TrackerListResponse, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_list(self, client: Agentex) -> None:
        with client.tracker.with_streaming_response.list() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            tracker = response.parse()
            assert_matches_type(TrackerListResponse, tracker, path=["response"])

        assert cast(Any, response.is_closed) is True


class TestAsyncTracker:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_retrieve(self, async_client: AsyncAgentex) -> None:
        tracker = await async_client.tracker.retrieve(
            "tracker_id",
        )
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tracker.with_raw_response.retrieve(
            "tracker_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        tracker = await response.parse()
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve(self, async_client: AsyncAgentex) -> None:
        async with async_client.tracker.with_streaming_response.retrieve(
            "tracker_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            tracker = await response.parse()
            assert_matches_type(AgentTaskTracker, tracker, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_retrieve(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `tracker_id` but received ''"):
            await async_client.tracker.with_raw_response.retrieve(
                "",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_update(self, async_client: AsyncAgentex) -> None:
        tracker = await async_client.tracker.update(
            tracker_id="tracker_id",
        )
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_update_with_all_params(self, async_client: AsyncAgentex) -> None:
        tracker = await async_client.tracker.update(
            tracker_id="tracker_id",
            last_processed_event_id="last_processed_event_id",
            status="status",
            status_reason="status_reason",
        )
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_update(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tracker.with_raw_response.update(
            tracker_id="tracker_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        tracker = await response.parse()
        assert_matches_type(AgentTaskTracker, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_update(self, async_client: AsyncAgentex) -> None:
        async with async_client.tracker.with_streaming_response.update(
            tracker_id="tracker_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            tracker = await response.parse()
            assert_matches_type(AgentTaskTracker, tracker, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_path_params_update(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `tracker_id` but received ''"):
            await async_client.tracker.with_raw_response.update(
                tracker_id="",
            )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_list(self, async_client: AsyncAgentex) -> None:
        tracker = await async_client.tracker.list()
        assert_matches_type(TrackerListResponse, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_list_with_all_params(self, async_client: AsyncAgentex) -> None:
        tracker = await async_client.tracker.list(
            agent_id="agent_id",
            task_id="task_id",
        )
        assert_matches_type(TrackerListResponse, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_list(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tracker.with_raw_response.list()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        tracker = await response.parse()
        assert_matches_type(TrackerListResponse, tracker, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_list(self, async_client: AsyncAgentex) -> None:
        async with async_client.tracker.with_streaming_response.list() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            tracker = await response.parse()
            assert_matches_type(TrackerListResponse, tracker, path=["response"])

        assert cast(Any, response.is_closed) is True
