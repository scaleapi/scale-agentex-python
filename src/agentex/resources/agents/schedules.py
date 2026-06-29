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
from ...types.agents import schedule_list_params, schedule_create_params
from ...types.agents.schedule_list_response import ScheduleListResponse
from ...types.agents.schedule_create_response import ScheduleCreateResponse

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

          name: Human-readable name, unique per agent (e.g. 'daily-granola-summary').

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

          name: Human-readable name, unique per agent (e.g. 'daily-granola-summary').

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


class SchedulesResourceWithRawResponse:
    def __init__(self, schedules: SchedulesResource) -> None:
        self._schedules = schedules

        self.create = to_raw_response_wrapper(
            schedules.create,
        )
        self.list = to_raw_response_wrapper(
            schedules.list,
        )


class AsyncSchedulesResourceWithRawResponse:
    def __init__(self, schedules: AsyncSchedulesResource) -> None:
        self._schedules = schedules

        self.create = async_to_raw_response_wrapper(
            schedules.create,
        )
        self.list = async_to_raw_response_wrapper(
            schedules.list,
        )


class SchedulesResourceWithStreamingResponse:
    def __init__(self, schedules: SchedulesResource) -> None:
        self._schedules = schedules

        self.create = to_streamed_response_wrapper(
            schedules.create,
        )
        self.list = to_streamed_response_wrapper(
            schedules.list,
        )


class AsyncSchedulesResourceWithStreamingResponse:
    def __init__(self, schedules: AsyncSchedulesResource) -> None:
        self._schedules = schedules

        self.create = async_to_streamed_response_wrapper(
            schedules.create,
        )
        self.list = async_to_streamed_response_wrapper(
            schedules.list,
        )
