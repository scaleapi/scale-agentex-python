# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from agentex._utils import parse_datetime
from agentex.types.agents import (
    ScheduleListResponse,
    ScheduleSkipResponse,
    SchedulePauseResponse,
    ScheduleCreateResponse,
    ScheduleResumeResponse,
    ScheduleUnskipResponse,
    ScheduleUpdateResponse,
    ScheduleTriggerResponse,
    ScheduleRetrieveResponse,
    SchedulePauseByNameResponse,
    ScheduleResumeByNameResponse,
    ScheduleUpdateByNameResponse,
    ScheduleTriggerByNameResponse,
    ScheduleRetrieveByNameResponse,
)
from agentex.types.shared import DeleteResponse

from ...utils import assert_matches_type

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
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleRetrieveResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_retrieve(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.retrieve(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            client.agents.schedules.with_raw_response.retrieve(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_update(self, client: Agentex) -> None:
        schedule = client.agents.schedules.update(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleUpdateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_update_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.update(
            schedule_id="schedule_id",
            agent_id="agent_id",
            cron_expression="cron_expression",
            description="description",
            end_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            initial_input={
                "content": "content",
                "author": "user",
                "type": "text",
            },
            interval_seconds=1,
            name="name",
            paused=True,
            start_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            task_metadata={"foo": "bar"},
            task_params={"foo": "bar"},
            timezone="timezone",
        )
        assert_matches_type(ScheduleUpdateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_update(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.update(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleUpdateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_update(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.update(
            schedule_id="schedule_id",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleUpdateResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_update(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.update(
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            client.agents.schedules.with_raw_response.update(
                schedule_id="",
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
            include_live=True,
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
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_delete(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.delete(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            client.agents.schedules.with_raw_response.delete(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_delete_by_name(self, client: Agentex) -> None:
        schedule = client.agents.schedules.delete_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_delete_by_name(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.delete_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_delete_by_name(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.delete_by_name(
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
    def test_path_params_delete_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.delete_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.delete_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_pause(self, client: Agentex) -> None:
        schedule = client.agents.schedules.pause(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_pause_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.pause(
            schedule_id="schedule_id",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_pause(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.pause(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            client.agents.schedules.with_raw_response.pause(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_pause_by_name(self, client: Agentex) -> None:
        schedule = client.agents.schedules.pause_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(SchedulePauseByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_pause_by_name_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.pause_by_name(
            name="name",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(SchedulePauseByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_pause_by_name(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.pause_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(SchedulePauseByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_pause_by_name(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.pause_by_name(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(SchedulePauseByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_pause_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.pause_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.pause_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_resume(self, client: Agentex) -> None:
        schedule = client.agents.schedules.resume(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_resume_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.resume(
            schedule_id="schedule_id",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_resume(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.resume(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            client.agents.schedules.with_raw_response.resume(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_resume_by_name(self, client: Agentex) -> None:
        schedule = client.agents.schedules.resume_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleResumeByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_resume_by_name_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.resume_by_name(
            name="name",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(ScheduleResumeByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_resume_by_name(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.resume_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleResumeByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_resume_by_name(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.resume_by_name(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleResumeByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_resume_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.resume_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.resume_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_retrieve_by_name(self, client: Agentex) -> None:
        schedule = client.agents.schedules.retrieve_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleRetrieveByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_retrieve_by_name(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.retrieve_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleRetrieveByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_retrieve_by_name(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.retrieve_by_name(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleRetrieveByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_retrieve_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.retrieve_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.retrieve_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_skip(self, client: Agentex) -> None:
        schedule = client.agents.schedules.skip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        )
        assert_matches_type(ScheduleSkipResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_skip(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.skip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleSkipResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_skip(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.skip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleSkipResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_skip(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.skip(
                schedule_id="schedule_id",
                agent_id="",
                scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            client.agents.schedules.with_raw_response.skip(
                schedule_id="",
                agent_id="agent_id",
                scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_trigger(self, client: Agentex) -> None:
        schedule = client.agents.schedules.trigger(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleTriggerResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_trigger(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.trigger(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            client.agents.schedules.with_raw_response.trigger(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_trigger_by_name(self, client: Agentex) -> None:
        schedule = client.agents.schedules.trigger_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleTriggerByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_trigger_by_name(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.trigger_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleTriggerByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_trigger_by_name(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.trigger_by_name(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleTriggerByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_trigger_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.trigger_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            client.agents.schedules.with_raw_response.trigger_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_unskip(self, client: Agentex) -> None:
        schedule = client.agents.schedules.unskip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        )
        assert_matches_type(ScheduleUnskipResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_unskip(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.unskip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleUnskipResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_unskip(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.unskip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleUnskipResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_unskip(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.unskip(
                schedule_id="schedule_id",
                agent_id="",
                scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            client.agents.schedules.with_raw_response.unskip(
                schedule_id="",
                agent_id="agent_id",
                scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_update_by_name(self, client: Agentex) -> None:
        schedule = client.agents.schedules.update_by_name(
            path_name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleUpdateByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_update_by_name_with_all_params(self, client: Agentex) -> None:
        schedule = client.agents.schedules.update_by_name(
            path_name="name",
            agent_id="agent_id",
            cron_expression="cron_expression",
            description="description",
            end_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            initial_input={
                "content": "content",
                "author": "user",
                "type": "text",
            },
            interval_seconds=1,
            body_name="name",
            paused=True,
            start_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            task_metadata={"foo": "bar"},
            task_params={"foo": "bar"},
            timezone="timezone",
        )
        assert_matches_type(ScheduleUpdateByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_update_by_name(self, client: Agentex) -> None:
        response = client.agents.schedules.with_raw_response.update_by_name(
            path_name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = response.parse()
        assert_matches_type(ScheduleUpdateByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_update_by_name(self, client: Agentex) -> None:
        with client.agents.schedules.with_streaming_response.update_by_name(
            path_name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = response.parse()
            assert_matches_type(ScheduleUpdateByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_update_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            client.agents.schedules.with_raw_response.update_by_name(
                path_name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `path_name` but received ''"):
            client.agents.schedules.with_raw_response.update_by_name(
                path_name="",
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
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleRetrieveResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.retrieve(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.retrieve(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_update(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.update(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleUpdateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_update_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.update(
            schedule_id="schedule_id",
            agent_id="agent_id",
            cron_expression="cron_expression",
            description="description",
            end_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            initial_input={
                "content": "content",
                "author": "user",
                "type": "text",
            },
            interval_seconds=1,
            name="name",
            paused=True,
            start_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            task_metadata={"foo": "bar"},
            task_params={"foo": "bar"},
            timezone="timezone",
        )
        assert_matches_type(ScheduleUpdateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_update(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.update(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleUpdateResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_update(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.update(
            schedule_id="schedule_id",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleUpdateResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_update(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.update(
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.update(
                schedule_id="",
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
            include_live=True,
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
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_delete(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.delete(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.delete(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_delete_by_name(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.delete_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_delete_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.delete_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(DeleteResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_delete_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.delete_by_name(
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
    async def test_path_params_delete_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.delete_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.delete_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_pause(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.pause(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_pause_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.pause(
            schedule_id="schedule_id",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(SchedulePauseResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_pause(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.pause(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.pause(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_pause_by_name(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.pause_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(SchedulePauseByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_pause_by_name_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.pause_by_name(
            name="name",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(SchedulePauseByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_pause_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.pause_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(SchedulePauseByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_pause_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.pause_by_name(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(SchedulePauseByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_pause_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.pause_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.pause_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_resume(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.resume(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_resume_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.resume(
            schedule_id="schedule_id",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(ScheduleResumeResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_resume(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.resume(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.resume(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_resume_by_name(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.resume_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleResumeByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_resume_by_name_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.resume_by_name(
            name="name",
            agent_id="agent_id",
            note="note",
        )
        assert_matches_type(ScheduleResumeByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_resume_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.resume_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleResumeByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_resume_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.resume_by_name(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleResumeByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_resume_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.resume_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.resume_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.retrieve_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleRetrieveByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.retrieve_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleRetrieveByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.retrieve_by_name(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleRetrieveByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.retrieve_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.retrieve_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_skip(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.skip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        )
        assert_matches_type(ScheduleSkipResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_skip(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.skip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleSkipResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_skip(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.skip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleSkipResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_skip(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.skip(
                schedule_id="schedule_id",
                agent_id="",
                scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.skip(
                schedule_id="",
                agent_id="agent_id",
                scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_trigger(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.trigger(
            schedule_id="schedule_id",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleTriggerResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_trigger(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.trigger(
            schedule_id="schedule_id",
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
            schedule_id="schedule_id",
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
                schedule_id="schedule_id",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.trigger(
                schedule_id="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_trigger_by_name(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.trigger_by_name(
            name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleTriggerByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_trigger_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.trigger_by_name(
            name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleTriggerByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_trigger_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.trigger_by_name(
            name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleTriggerByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_trigger_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.trigger_by_name(
                name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `name` but received ''"):
            await async_client.agents.schedules.with_raw_response.trigger_by_name(
                name="",
                agent_id="agent_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_unskip(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.unskip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        )
        assert_matches_type(ScheduleUnskipResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_unskip(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.unskip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleUnskipResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_unskip(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.unskip(
            schedule_id="schedule_id",
            agent_id="agent_id",
            scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleUnskipResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_unskip(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.unskip(
                schedule_id="schedule_id",
                agent_id="",
                scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `schedule_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.unskip(
                schedule_id="",
                agent_id="agent_id",
                scheduled_time=parse_datetime("2019-12-27T18:11:19.117Z"),
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_update_by_name(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.update_by_name(
            path_name="name",
            agent_id="agent_id",
        )
        assert_matches_type(ScheduleUpdateByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_update_by_name_with_all_params(self, async_client: AsyncAgentex) -> None:
        schedule = await async_client.agents.schedules.update_by_name(
            path_name="name",
            agent_id="agent_id",
            cron_expression="cron_expression",
            description="description",
            end_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            initial_input={
                "content": "content",
                "author": "user",
                "type": "text",
            },
            interval_seconds=1,
            body_name="name",
            paused=True,
            start_at=parse_datetime("2019-12-27T18:11:19.117Z"),
            task_metadata={"foo": "bar"},
            task_params={"foo": "bar"},
            timezone="timezone",
        )
        assert_matches_type(ScheduleUpdateByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_update_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.agents.schedules.with_raw_response.update_by_name(
            path_name="name",
            agent_id="agent_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        schedule = await response.parse()
        assert_matches_type(ScheduleUpdateByNameResponse, schedule, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_update_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.agents.schedules.with_streaming_response.update_by_name(
            path_name="name",
            agent_id="agent_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            schedule = await response.parse()
            assert_matches_type(ScheduleUpdateByNameResponse, schedule, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_update_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `agent_id` but received ''"):
            await async_client.agents.schedules.with_raw_response.update_by_name(
                path_name="name",
                agent_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `path_name` but received ''"):
            await async_client.agents.schedules.with_raw_response.update_by_name(
                path_name="",
                agent_id="agent_id",
            )
