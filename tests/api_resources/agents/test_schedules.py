# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type
from agentex._utils import parse_datetime
from agentex.types.agents import (
    ScheduleListResponse,
    SchedulePauseResponse,
    ScheduleCreateResponse,
    ScheduleResumeResponse,
    ScheduleTriggerResponse,
    ScheduleRetrieveResponse,
)
from agentex.types.shared import DeleteResponse

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestSchedules:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_create(self, client: Agentex) -> None:
        schedule = client.agents.schedules.create(
            agent_id="agent_id",
            initial_input={"content": "content"},
            name="name",
        )
        assert_matches_type(ScheduleCreateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_create_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.create(
            agent_id="agent_id",
            initial_input={
                "content": "content",
                "author": "user",
                "type": "text",
            },
            name="name",
            cron_expression="cron_expression",
            description="description",
            end_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            interval_seconds=1,
            paused=True,
            start_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            task_metadata={"foo": "bar"},
            task_params={"foo": "bar"},
            timezone="timezone",
        )
        assert_matches_type(ScheduleCreateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_create(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.create(
            agent_id="agent_id",
            initial_input={"content": "content"},
            name="name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleCreateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_create(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.create(
            agent_id="agent_id",
            initial_input={"content": "content"},
            name="name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleCreateResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_create(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.create(
                agent_id="",
                initial_input={"content": "content"},
                name="name",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_retrieve(self, client: Agentex) -> None:
        schedule = client.agents.schedules.retrieve(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleRetrieveResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_retrieve(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.retrieve(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleRetrieveResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_retrieve(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.retrieve(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleRetrieveResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_retrieve(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.retrieve(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.retrieve(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_list(self, client: Agentex) -> None:
        schedule = client.agents.schedules.list(
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleListResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_list_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.list(
            agent_id="agent_id",
            limit=1,
        )
        assert_matches_type(ScheduleListResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_list(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.list(
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleListResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_list(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.list(
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleListResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_list(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.list(
                agent_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_delete(self, client: Agentex) -> None:
        schedule = client.agents.schedules.delete(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_delete(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.delete(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_delete(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.delete(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(DeleteResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_delete(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.delete(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.delete(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_pause(self, client: Agentex) -> None:
        schedule = client.agents.schedules.pause(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_pause_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.pause(
            name="name",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_pause(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.pause(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_pause(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.pause(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_pause(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.pause(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.pause(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_resume(self, client: Agentex) -> None:
        schedule = client.agents.schedules.resume(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_resume_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.resume(
            name="name",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_resume(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.resume(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_resume(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.resume(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_resume(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.resume(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.resume(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_trigger(self, client: Agentex) -> None:
        schedule = client.agents.schedules.trigger(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleTriggerResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_trigger(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.trigger(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleTriggerResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_trigger(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.trigger(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleTriggerResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_trigger(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.trigger(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.trigger(
                name="",
                agent_id="agent_id",
            )


class TestAsyncSchedules:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_create(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.create(
            agent_id="agent_id",
            initial_input={"content": "content"},
            name="name",
        )
        assert_matches_type(ScheduleCreateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_create_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.create(
            agent_id="agent_id",
            initial_input={
                "content": "content",
                "author": "user",
                "type": "text",
            },
            name="name",
            cron_expression="cron_expression",
            description="description",
            end_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            interval_seconds=1,
            paused=True,
            start_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            task_metadata={"foo": "bar"},
            task_params={"foo": "bar"},
            timezone="timezone",
        )
        assert_matches_type(ScheduleCreateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_create(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.create(
            agent_id="agent_id",
            initial_input={"content": "content"},
            name="name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleCreateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_create(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.create(
            agent_id="agent_id",
            initial_input={"content": "content"},
            name="name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleCreateResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_create(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.create(
                agent_id="",
                initial_input={"content": "content"},
                name="name",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_retrieve(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.retrieve(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleRetrieveResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.retrieve(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleRetrieveResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.retrieve(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleRetrieveResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_retrieve(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.retrieve(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.retrieve(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_list(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.list(
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleListResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_list_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.list(
            agent_id="agent_id",
            limit=1,
        )
        assert_matches_type(ScheduleListResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_list(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.list(
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleListResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_list(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.list(
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleListResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_list(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.list(
                agent_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_delete(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.delete(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_delete(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.delete(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_delete(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.delete(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(DeleteResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_delete(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.delete(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.delete(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_pause(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.pause(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_pause_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.pause(
            name="name",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_pause(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.pause(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_pause(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.pause(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_pause(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.pause(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.pause(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_resume(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.resume(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_resume_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.resume(
            name="name",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_resume(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.resume(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_resume(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.resume(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_resume(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.resume(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.resume(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_trigger(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.trigger(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleTriggerResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_trigger(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.trigger(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleTriggerResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_trigger(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.trigger(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleTriggerResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_trigger(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.trigger(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.trigger(
                name="",
                agent_id="agent_id",
            )
