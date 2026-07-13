# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import path_template, maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.agents import (
    schedule_list_params,
    schedule_skip_params,
    schedule_pause_params,
    schedule_create_params,
    schedule_resume_params,
    schedule_unskip_params,
    schedule_update_params,
    schedule_pause_by_name_params,
    schedule_resume_by_name_params,
    schedule_update_by_name_params,
)
from ...types.shared.delete_response import DeleteResponse
from ...types.agents.schedule_list_response import ScheduleListResponse
from ...types.agents.schedule_skip_response import ScheduleSkipResponse
from ...types.agents.schedule_pause_response import SchedulePauseResponse
from ...types.agents.schedule_create_response import ScheduleCreateResponse
from ...types.agents.schedule_resume_response import ScheduleResumeResponse
from ...types.agents.schedule_unskip_response import ScheduleUnskipResponse
from ...types.agents.schedule_update_response import ScheduleUpdateResponse
from ...types.agents.schedule_trigger_response import ScheduleTriggerResponse
from ...types.agents.schedule_retrieve_response import ScheduleRetrieveResponse
from ...types.agents.schedule_pause_by_name_response import SchedulePauseByNameResponse
from ...types.agents.schedule_resume_by_name_response import ScheduleResumeByNameResponse
from ...types.agents.schedule_update_by_name_response import ScheduleUpdateByNameResponse
from ...types.agents.schedule_trigger_by_name_response import ScheduleTriggerByNameResponse
from ...types.agents.schedule_retrieve_by_name_response import ScheduleRetrieveByNameResponse

__all__ = ["SchedulesResource", "AsyncSchedulesResource"]


class SchedulesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> SchedulesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return SchedulesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SchedulesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return SchedulesResourceWithStreamingResponse(self)

    def create(
        self,
        agent_id: str,
        *,
        initial_input: schedule_create_params.InitialInput,
        name: str,
        cron_expression: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_at: Union[str, datetime, None] | Omit = omit,
        interval_seconds: Optional[int] | Omit = omit,
        paused: bool | Omit = omit,
        start_at: Union[str, datetime, None] | Omit = omit,
        task_metadata: Optional[Dict[str, object]] | Omit = omit,
        task_params: Optional[Dict[str, object]] | Omit = omit,
        timezone: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleCreateResponse:
        """
        Create a recurring schedule that starts a fresh agent run on each fire.

        Args:
          initial_input: The first input delivered to each created task.

          name: Human-readable name, unique among active schedules for the agent.

          cron_expression: Cron expression for the cadence (e.g. '0 17 \\** \\** MON-FRI'). Mutually exclusive
              with interval_seconds.

          description: Optional description of what this schedule does.

          end_at: When the schedule should stop being active.

          interval_seconds: Interval cadence in seconds. Mutually exclusive with cron_expression.

          paused: Whether to create the schedule in a paused state.

          start_at: When the schedule should start being active.

          task_metadata: Metadata copied onto each created task at fire time.

          task_params: Resolved config forwarded as task `params` at fire time.

          timezone: IANA timezone the cron expression is evaluated in (e.g. 'America/New_York').

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return self._post(
            path_template("/agents/{agent_id}/schedules", agent_id=agent_id),
            body=maybe_transform(
                {
                    "initial_input": initial_input,
                    "name": name,
                    "cron_expression": cron_expression,
                    "description": description,
                    "end_at": end_at,
                    "interval_seconds": interval_seconds,
                    "paused": paused,
                    "start_at": start_at,
                    "task_metadata": task_metadata,
                    "task_params": task_params,
                    "timezone": timezone,
                },
                schedule_create_params.ScheduleCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleCreateResponse,
        )

    def retrieve(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleRetrieveResponse:
        """
        Get a run schedule by its id.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return self._get(
            path_template("/agents/{agent_id}/schedules/{schedule_id}", agent_id=agent_id, schedule_id=schedule_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleRetrieveResponse,
        )

    def update(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        cron_expression: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_at: Union[str, datetime, None] | Omit = omit,
        initial_input: Optional[schedule_update_params.InitialInput] | Omit = omit,
        interval_seconds: Optional[int] | Omit = omit,
        name: Optional[str] | Omit = omit,
        paused: Optional[bool] | Omit = omit,
        start_at: Union[str, datetime, None] | Omit = omit,
        task_metadata: Optional[Dict[str, object]] | Omit = omit,
        task_params: Optional[Dict[str, object]] | Omit = omit,
        timezone: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleUpdateResponse:
        """
        Partially update a run schedule's definition (cadence, window, input, etc.).

        Args:
          cron_expression: New cron cadence. Mutually exclusive with interval_seconds.

          description: Optional description of what this schedule does.

          end_at: When the schedule should stop being active.

          initial_input: The first input delivered to each freshly created scheduled task.

          interval_seconds: New interval cadence in seconds. Mutually exclusive with cron_expression.

          name: Human-readable name, unique among active schedules for the agent.

          paused: Pause/resume the schedule as part of the update.

          start_at: When the schedule should start being active.

          task_metadata: Metadata copied onto each created task at fire time.

          task_params: Resolved config forwarded as task `params` at fire time.

          timezone: IANA timezone the cron expression is evaluated in.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return self._patch(
            path_template("/agents/{agent_id}/schedules/{schedule_id}", agent_id=agent_id, schedule_id=schedule_id),
            body=maybe_transform(
                {
                    "cron_expression": cron_expression,
                    "description": description,
                    "end_at": end_at,
                    "initial_input": initial_input,
                    "interval_seconds": interval_seconds,
                    "name": name,
                    "paused": paused,
                    "start_at": start_at,
                    "task_metadata": task_metadata,
                    "task_params": task_params,
                    "timezone": timezone,
                },
                schedule_update_params.ScheduleUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleUpdateResponse,
        )

    def list(
        self,
        agent_id: str,
        *,
        limit: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleListResponse:
        """
        List run schedules for an agent.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return self._get(
            path_template("/agents/{agent_id}/schedules", agent_id=agent_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"limit": limit}, schedule_list_params.ScheduleListParams),
            ),
            cast_to=ScheduleListResponse,
        )

    def delete(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeleteResponse:
        """
        Delete a run schedule permanently.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return self._delete(
            path_template("/agents/{agent_id}/schedules/{schedule_id}", agent_id=agent_id, schedule_id=schedule_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    def delete_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeleteResponse:
        """
        Delete a run schedule by its active name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._delete(
            path_template("/agents/{agent_id}/schedules/name/{name}", agent_id=agent_id, name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    def pause(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        note: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SchedulePauseResponse:
        """
        Pause a run schedule so it stops firing.

        Args:
          note: Optional note explaining the pause.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/pause", agent_id=agent_id, schedule_id=schedule_id
            ),
            body=maybe_transform({"note": note}, schedule_pause_params.SchedulePauseParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SchedulePauseResponse,
        )

    def pause_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        note: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SchedulePauseByNameResponse:
        """
        Pause a run schedule by its active name.

        Args:
          note: Optional note explaining the pause.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._post(
            path_template("/agents/{agent_id}/schedules/name/{name}/pause", agent_id=agent_id, name=name),
            body=maybe_transform({"note": note}, schedule_pause_by_name_params.SchedulePauseByNameParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SchedulePauseByNameResponse,
        )

    def resume(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        note: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleResumeResponse:
        """
        Resume a paused run schedule so it fires again.

        Args:
          note: Optional note explaining the resume.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/resume", agent_id=agent_id, schedule_id=schedule_id
            ),
            body=maybe_transform({"note": note}, schedule_resume_params.ScheduleResumeParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleResumeResponse,
        )

    def resume_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        note: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleResumeByNameResponse:
        """
        Resume a paused run schedule by its active name.

        Args:
          note: Optional note explaining the resume.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._post(
            path_template("/agents/{agent_id}/schedules/name/{name}/resume", agent_id=agent_id, name=name),
            body=maybe_transform({"note": note}, schedule_resume_by_name_params.ScheduleResumeByNameParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleResumeByNameResponse,
        )

    def retrieve_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleRetrieveByNameResponse:
        """
        Get a run schedule by its active name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._get(
            path_template("/agents/{agent_id}/schedules/name/{name}", agent_id=agent_id, name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleRetrieveByNameResponse,
        )

    def skip(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        scheduled_time: Union[str, datetime],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleSkipResponse:
        """
        Skip a recurring fire of the schedule.

        Args:
          scheduled_time: Specific scheduled fire time to skip.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/skip", agent_id=agent_id, schedule_id=schedule_id
            ),
            body=maybe_transform({"scheduled_time": scheduled_time}, schedule_skip_params.ScheduleSkipParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleSkipResponse,
        )

    def trigger(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleTriggerResponse:
        """
        Trigger an immediate, out-of-band run of the schedule (in addition to its
        cadence).

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/trigger", agent_id=agent_id, schedule_id=schedule_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleTriggerResponse,
        )

    def trigger_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleTriggerByNameResponse:
        """
        Trigger an immediate, out-of-band run of the schedule by its active name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._post(
            path_template("/agents/{agent_id}/schedules/name/{name}/trigger", agent_id=agent_id, name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleTriggerByNameResponse,
        )

    def unskip(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        scheduled_time: Union[str, datetime],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleUnskipResponse:
        """
        Remove a skip for a recurring fire of the schedule.

        Args:
          scheduled_time: Specific scheduled fire time to unskip.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/unskip", agent_id=agent_id, schedule_id=schedule_id
            ),
            body=maybe_transform({"scheduled_time": scheduled_time}, schedule_unskip_params.ScheduleUnskipParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleUnskipResponse,
        )

    def update_by_name(
        self,
        path_name: str,
        *,
        agent_id: str,
        cron_expression: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_at: Union[str, datetime, None] | Omit = omit,
        initial_input: Optional[schedule_update_by_name_params.InitialInput] | Omit = omit,
        interval_seconds: Optional[int] | Omit = omit,
        body_name: Optional[str] | Omit = omit,
        paused: Optional[bool] | Omit = omit,
        start_at: Union[str, datetime, None] | Omit = omit,
        task_metadata: Optional[Dict[str, object]] | Omit = omit,
        task_params: Optional[Dict[str, object]] | Omit = omit,
        timezone: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleUpdateByNameResponse:
        """
        Partially update a run schedule's definition by its active name.

        Args:
          cron_expression: New cron cadence. Mutually exclusive with interval_seconds.

          description: Optional description of what this schedule does.

          end_at: When the schedule should stop being active.

          initial_input: The first input delivered to each freshly created scheduled task.

          interval_seconds: New interval cadence in seconds. Mutually exclusive with cron_expression.

          body_name: Human-readable name, unique among active schedules for the agent.

          paused: Pause/resume the schedule as part of the update.

          start_at: When the schedule should start being active.

          task_metadata: Metadata copied onto each created task at fire time.

          task_params: Resolved config forwarded as task `params` at fire time.

          timezone: IANA timezone the cron expression is evaluated in.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not path_name:
            raise ValueError(f"Expected a non-empty value for `path_name` but received {path_name!r}")
        return self._patch(
            path_template("/agents/{agent_id}/schedules/name/{path_name}", agent_id=agent_id, path_name=path_name),
            body=maybe_transform(
                {
                    "cron_expression": cron_expression,
                    "description": description,
                    "end_at": end_at,
                    "initial_input": initial_input,
                    "interval_seconds": interval_seconds,
                    "body_name": body_name,
                    "paused": paused,
                    "start_at": start_at,
                    "task_metadata": task_metadata,
                    "task_params": task_params,
                    "timezone": timezone,
                },
                schedule_update_by_name_params.ScheduleUpdateByNameParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleUpdateByNameResponse,
        )


class AsyncSchedulesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncSchedulesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncSchedulesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSchedulesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return AsyncSchedulesResourceWithStreamingResponse(self)

    async def create(
        self,
        agent_id: str,
        *,
        initial_input: schedule_create_params.InitialInput,
        name: str,
        cron_expression: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_at: Union[str, datetime, None] | Omit = omit,
        interval_seconds: Optional[int] | Omit = omit,
        paused: bool | Omit = omit,
        start_at: Union[str, datetime, None] | Omit = omit,
        task_metadata: Optional[Dict[str, object]] | Omit = omit,
        task_params: Optional[Dict[str, object]] | Omit = omit,
        timezone: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleCreateResponse:
        """
        Create a recurring schedule that starts a fresh agent run on each fire.

        Args:
          initial_input: The first input delivered to each created task.

          name: Human-readable name, unique among active schedules for the agent.

          cron_expression: Cron expression for the cadence (e.g. '0 17 \\** \\** MON-FRI'). Mutually exclusive
              with interval_seconds.

          description: Optional description of what this schedule does.

          end_at: When the schedule should stop being active.

          interval_seconds: Interval cadence in seconds. Mutually exclusive with cron_expression.

          paused: Whether to create the schedule in a paused state.

          start_at: When the schedule should start being active.

          task_metadata: Metadata copied onto each created task at fire time.

          task_params: Resolved config forwarded as task `params` at fire time.

          timezone: IANA timezone the cron expression is evaluated in (e.g. 'America/New_York').

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return await self._post(
            path_template("/agents/{agent_id}/schedules", agent_id=agent_id),
            body=await async_maybe_transform(
                {
                    "initial_input": initial_input,
                    "name": name,
                    "cron_expression": cron_expression,
                    "description": description,
                    "end_at": end_at,
                    "interval_seconds": interval_seconds,
                    "paused": paused,
                    "start_at": start_at,
                    "task_metadata": task_metadata,
                    "task_params": task_params,
                    "timezone": timezone,
                },
                schedule_create_params.ScheduleCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleCreateResponse,
        )

    async def retrieve(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleRetrieveResponse:
        """
        Get a run schedule by its id.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return await self._get(
            path_template("/agents/{agent_id}/schedules/{schedule_id}", agent_id=agent_id, schedule_id=schedule_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleRetrieveResponse,
        )

    async def update(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        cron_expression: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_at: Union[str, datetime, None] | Omit = omit,
        initial_input: Optional[schedule_update_params.InitialInput] | Omit = omit,
        interval_seconds: Optional[int] | Omit = omit,
        name: Optional[str] | Omit = omit,
        paused: Optional[bool] | Omit = omit,
        start_at: Union[str, datetime, None] | Omit = omit,
        task_metadata: Optional[Dict[str, object]] | Omit = omit,
        task_params: Optional[Dict[str, object]] | Omit = omit,
        timezone: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleUpdateResponse:
        """
        Partially update a run schedule's definition (cadence, window, input, etc.).

        Args:
          cron_expression: New cron cadence. Mutually exclusive with interval_seconds.

          description: Optional description of what this schedule does.

          end_at: When the schedule should stop being active.

          initial_input: The first input delivered to each freshly created scheduled task.

          interval_seconds: New interval cadence in seconds. Mutually exclusive with cron_expression.

          name: Human-readable name, unique among active schedules for the agent.

          paused: Pause/resume the schedule as part of the update.

          start_at: When the schedule should start being active.

          task_metadata: Metadata copied onto each created task at fire time.

          task_params: Resolved config forwarded as task `params` at fire time.

          timezone: IANA timezone the cron expression is evaluated in.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return await self._patch(
            path_template("/agents/{agent_id}/schedules/{schedule_id}", agent_id=agent_id, schedule_id=schedule_id),
            body=await async_maybe_transform(
                {
                    "cron_expression": cron_expression,
                    "description": description,
                    "end_at": end_at,
                    "initial_input": initial_input,
                    "interval_seconds": interval_seconds,
                    "name": name,
                    "paused": paused,
                    "start_at": start_at,
                    "task_metadata": task_metadata,
                    "task_params": task_params,
                    "timezone": timezone,
                },
                schedule_update_params.ScheduleUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleUpdateResponse,
        )

    async def list(
        self,
        agent_id: str,
        *,
        limit: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleListResponse:
        """
        List run schedules for an agent.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return await self._get(
            path_template("/agents/{agent_id}/schedules", agent_id=agent_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"limit": limit}, schedule_list_params.ScheduleListParams),
            ),
            cast_to=ScheduleListResponse,
        )

    async def delete(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeleteResponse:
        """
        Delete a run schedule permanently.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return await self._delete(
            path_template("/agents/{agent_id}/schedules/{schedule_id}", agent_id=agent_id, schedule_id=schedule_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    async def delete_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeleteResponse:
        """
        Delete a run schedule by its active name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._delete(
            path_template("/agents/{agent_id}/schedules/name/{name}", agent_id=agent_id, name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    async def pause(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        note: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SchedulePauseResponse:
        """
        Pause a run schedule so it stops firing.

        Args:
          note: Optional note explaining the pause.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return await self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/pause", agent_id=agent_id, schedule_id=schedule_id
            ),
            body=await async_maybe_transform({"note": note}, schedule_pause_params.SchedulePauseParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SchedulePauseResponse,
        )

    async def pause_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        note: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SchedulePauseByNameResponse:
        """
        Pause a run schedule by its active name.

        Args:
          note: Optional note explaining the pause.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._post(
            path_template("/agents/{agent_id}/schedules/name/{name}/pause", agent_id=agent_id, name=name),
            body=await async_maybe_transform({"note": note}, schedule_pause_by_name_params.SchedulePauseByNameParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SchedulePauseByNameResponse,
        )

    async def resume(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        note: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleResumeResponse:
        """
        Resume a paused run schedule so it fires again.

        Args:
          note: Optional note explaining the resume.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return await self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/resume", agent_id=agent_id, schedule_id=schedule_id
            ),
            body=await async_maybe_transform({"note": note}, schedule_resume_params.ScheduleResumeParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleResumeResponse,
        )

    async def resume_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        note: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleResumeByNameResponse:
        """
        Resume a paused run schedule by its active name.

        Args:
          note: Optional note explaining the resume.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._post(
            path_template("/agents/{agent_id}/schedules/name/{name}/resume", agent_id=agent_id, name=name),
            body=await async_maybe_transform({"note": note}, schedule_resume_by_name_params.ScheduleResumeByNameParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleResumeByNameResponse,
        )

    async def retrieve_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleRetrieveByNameResponse:
        """
        Get a run schedule by its active name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._get(
            path_template("/agents/{agent_id}/schedules/name/{name}", agent_id=agent_id, name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleRetrieveByNameResponse,
        )

    async def skip(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        scheduled_time: Union[str, datetime],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleSkipResponse:
        """
        Skip a recurring fire of the schedule.

        Args:
          scheduled_time: Specific scheduled fire time to skip.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return await self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/skip", agent_id=agent_id, schedule_id=schedule_id
            ),
            body=await async_maybe_transform(
                {"scheduled_time": scheduled_time}, schedule_skip_params.ScheduleSkipParams
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleSkipResponse,
        )

    async def trigger(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleTriggerResponse:
        """
        Trigger an immediate, out-of-band run of the schedule (in addition to its
        cadence).

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return await self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/trigger", agent_id=agent_id, schedule_id=schedule_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleTriggerResponse,
        )

    async def trigger_by_name(
        self,
        name: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleTriggerByNameResponse:
        """
        Trigger an immediate, out-of-band run of the schedule by its active name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._post(
            path_template("/agents/{agent_id}/schedules/name/{name}/trigger", agent_id=agent_id, name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleTriggerByNameResponse,
        )

    async def unskip(
        self,
        schedule_id: str,
        *,
        agent_id: str,
        scheduled_time: Union[str, datetime],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleUnskipResponse:
        """
        Remove a skip for a recurring fire of the schedule.

        Args:
          scheduled_time: Specific scheduled fire time to unskip.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not schedule_id:
            raise ValueError(f"Expected a non-empty value for `schedule_id` but received {schedule_id!r}")
        return await self._post(
            path_template(
                "/agents/{agent_id}/schedules/{schedule_id}/unskip", agent_id=agent_id, schedule_id=schedule_id
            ),
            body=await async_maybe_transform(
                {"scheduled_time": scheduled_time}, schedule_unskip_params.ScheduleUnskipParams
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleUnskipResponse,
        )

    async def update_by_name(
        self,
        path_name: str,
        *,
        agent_id: str,
        cron_expression: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_at: Union[str, datetime, None] | Omit = omit,
        initial_input: Optional[schedule_update_by_name_params.InitialInput] | Omit = omit,
        interval_seconds: Optional[int] | Omit = omit,
        body_name: Optional[str] | Omit = omit,
        paused: Optional[bool] | Omit = omit,
        start_at: Union[str, datetime, None] | Omit = omit,
        task_metadata: Optional[Dict[str, object]] | Omit = omit,
        task_params: Optional[Dict[str, object]] | Omit = omit,
        timezone: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ScheduleUpdateByNameResponse:
        """
        Partially update a run schedule's definition by its active name.

        Args:
          cron_expression: New cron cadence. Mutually exclusive with interval_seconds.

          description: Optional description of what this schedule does.

          end_at: When the schedule should stop being active.

          initial_input: The first input delivered to each freshly created scheduled task.

          interval_seconds: New interval cadence in seconds. Mutually exclusive with cron_expression.

          body_name: Human-readable name, unique among active schedules for the agent.

          paused: Pause/resume the schedule as part of the update.

          start_at: When the schedule should start being active.

          task_metadata: Metadata copied onto each created task at fire time.

          task_params: Resolved config forwarded as task `params` at fire time.

          timezone: IANA timezone the cron expression is evaluated in.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not path_name:
            raise ValueError(f"Expected a non-empty value for `path_name` but received {path_name!r}")
        return await self._patch(
            path_template("/agents/{agent_id}/schedules/name/{path_name}", agent_id=agent_id, path_name=path_name),
            body=await async_maybe_transform(
                {
                    "cron_expression": cron_expression,
                    "description": description,
                    "end_at": end_at,
                    "initial_input": initial_input,
                    "interval_seconds": interval_seconds,
                    "body_name": body_name,
                    "paused": paused,
                    "start_at": start_at,
                    "task_metadata": task_metadata,
                    "task_params": task_params,
                    "timezone": timezone,
                },
                schedule_update_by_name_params.ScheduleUpdateByNameParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ScheduleUpdateByNameResponse,
        )


class SchedulesResourceWithRawResponse:
    def __init__(self, schedules: SchedulesResource) -> None:
        self._schedules = schedules

        self.create = to_raw_response_wrapper(
            schedules.create,
        )
        self.retrieve = to_raw_response_wrapper(
            schedules.retrieve,
        )
        self.update = to_raw_response_wrapper(
            schedules.update,
        )
        self.list = to_raw_response_wrapper(
            schedules.list,
        )
        self.delete = to_raw_response_wrapper(
            schedules.delete,
        )
        self.delete_by_name = to_raw_response_wrapper(
            schedules.delete_by_name,
        )
        self.pause = to_raw_response_wrapper(
            schedules.pause,
        )
        self.pause_by_name = to_raw_response_wrapper(
            schedules.pause_by_name,
        )
        self.resume = to_raw_response_wrapper(
            schedules.resume,
        )
        self.resume_by_name = to_raw_response_wrapper(
            schedules.resume_by_name,
        )
        self.retrieve_by_name = to_raw_response_wrapper(
            schedules.retrieve_by_name,
        )
        self.skip = to_raw_response_wrapper(
            schedules.skip,
        )
        self.trigger = to_raw_response_wrapper(
            schedules.trigger,
        )
        self.trigger_by_name = to_raw_response_wrapper(
            schedules.trigger_by_name,
        )
        self.unskip = to_raw_response_wrapper(
            schedules.unskip,
        )
        self.update_by_name = to_raw_response_wrapper(
            schedules.update_by_name,
        )


class AsyncSchedulesResourceWithRawResponse:
    def __init__(self, schedules: AsyncSchedulesResource) -> None:
        self._schedules = schedules

        self.create = async_to_raw_response_wrapper(
            schedules.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            schedules.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            schedules.update,
        )
        self.list = async_to_raw_response_wrapper(
            schedules.list,
        )
        self.delete = async_to_raw_response_wrapper(
            schedules.delete,
        )
        self.delete_by_name = async_to_raw_response_wrapper(
            schedules.delete_by_name,
        )
        self.pause = async_to_raw_response_wrapper(
            schedules.pause,
        )
        self.pause_by_name = async_to_raw_response_wrapper(
            schedules.pause_by_name,
        )
        self.resume = async_to_raw_response_wrapper(
            schedules.resume,
        )
        self.resume_by_name = async_to_raw_response_wrapper(
            schedules.resume_by_name,
        )
        self.retrieve_by_name = async_to_raw_response_wrapper(
            schedules.retrieve_by_name,
        )
        self.skip = async_to_raw_response_wrapper(
            schedules.skip,
        )
        self.trigger = async_to_raw_response_wrapper(
            schedules.trigger,
        )
        self.trigger_by_name = async_to_raw_response_wrapper(
            schedules.trigger_by_name,
        )
        self.unskip = async_to_raw_response_wrapper(
            schedules.unskip,
        )
        self.update_by_name = async_to_raw_response_wrapper(
            schedules.update_by_name,
        )


class SchedulesResourceWithStreamingResponse:
    def __init__(self, schedules: SchedulesResource) -> None:
        self._schedules = schedules

        self.create = to_streamed_response_wrapper(
            schedules.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            schedules.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            schedules.update,
        )
        self.list = to_streamed_response_wrapper(
            schedules.list,
        )
        self.delete = to_streamed_response_wrapper(
            schedules.delete,
        )
        self.delete_by_name = to_streamed_response_wrapper(
            schedules.delete_by_name,
        )
        self.pause = to_streamed_response_wrapper(
            schedules.pause,
        )
        self.pause_by_name = to_streamed_response_wrapper(
            schedules.pause_by_name,
        )
        self.resume = to_streamed_response_wrapper(
            schedules.resume,
        )
        self.resume_by_name = to_streamed_response_wrapper(
            schedules.resume_by_name,
        )
        self.retrieve_by_name = to_streamed_response_wrapper(
            schedules.retrieve_by_name,
        )
        self.skip = to_streamed_response_wrapper(
            schedules.skip,
        )
        self.trigger = to_streamed_response_wrapper(
            schedules.trigger,
        )
        self.trigger_by_name = to_streamed_response_wrapper(
            schedules.trigger_by_name,
        )
        self.unskip = to_streamed_response_wrapper(
            schedules.unskip,
        )
        self.update_by_name = to_streamed_response_wrapper(
            schedules.update_by_name,
        )


class AsyncSchedulesResourceWithStreamingResponse:
    def __init__(self, schedules: AsyncSchedulesResource) -> None:
        self._schedules = schedules

        self.create = async_to_streamed_response_wrapper(
            schedules.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            schedules.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            schedules.update,
        )
        self.list = async_to_streamed_response_wrapper(
            schedules.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            schedules.delete,
        )
        self.delete_by_name = async_to_streamed_response_wrapper(
            schedules.delete_by_name,
        )
        self.pause = async_to_streamed_response_wrapper(
            schedules.pause,
        )
        self.pause_by_name = async_to_streamed_response_wrapper(
            schedules.pause_by_name,
        )
        self.resume = async_to_streamed_response_wrapper(
            schedules.resume,
        )
        self.resume_by_name = async_to_streamed_response_wrapper(
            schedules.resume_by_name,
        )
        self.retrieve_by_name = async_to_streamed_response_wrapper(
            schedules.retrieve_by_name,
        )
        self.skip = async_to_streamed_response_wrapper(
            schedules.skip,
        )
        self.trigger = async_to_streamed_response_wrapper(
            schedules.trigger,
        )
        self.trigger_by_name = async_to_streamed_response_wrapper(
            schedules.trigger_by_name,
        )
        self.unskip = async_to_streamed_response_wrapper(
            schedules.unskip,
        )
        self.update_by_name = async_to_streamed_response_wrapper(
            schedules.update_by_name,
        )
