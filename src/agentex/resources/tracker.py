# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

import httpx

from ..types import tracker_list_params, tracker_update_params
from .._types import NOT_GIVEN, Body, Query, Headers, NotGiven
from .._utils import maybe_transform, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._base_client import make_request_options
from ..types.agent_task_tracker import AgentTaskTracker
from ..types.tracker_list_response import TrackerListResponse

__all__ = ["TrackerResource", "AsyncTrackerResource"]


class TrackerResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> TrackerResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/agentex-python#accessing-raw-response-data-eg-headers
        """
        return TrackerResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TrackerResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/agentex-python#with_streaming_response
        """
        return TrackerResourceWithStreamingResponse(self)

    def retrieve(
        self,
        tracker_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentTaskTracker:
        """
        Get agent task tracker by tracker ID

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not tracker_id:
            raise ValueError(f"Expected a non-empty value for `tracker_id` but received {tracker_id!r}")
        return self._get(
            f"/tracker/{tracker_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentTaskTracker,
        )

    def update(
        self,
        tracker_id: str,
        *,
        last_processed_event_id: Optional[str] | NotGiven = NOT_GIVEN,
        status: Optional[str] | NotGiven = NOT_GIVEN,
        status_reason: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentTaskTracker:
        """
        Update agent task tracker by tracker ID

        Args:
          last_processed_event_id: The most recent processed event ID (omit to leave unchanged)

          status: Processing status

          status_reason: Optional status reason

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not tracker_id:
            raise ValueError(f"Expected a non-empty value for `tracker_id` but received {tracker_id!r}")
        return self._put(
            f"/tracker/{tracker_id}",
            body=maybe_transform(
                {
                    "last_processed_event_id": last_processed_event_id,
                    "status": status,
                    "status_reason": status_reason,
                },
                tracker_update_params.TrackerUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentTaskTracker,
        )

    def list(
        self,
        *,
        agent_id: Optional[str] | NotGiven = NOT_GIVEN,
        task_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> TrackerListResponse:
        """
        List all agent task trackers, optionally filtered by query parameters.

        Args:
          agent_id: Agent ID

          task_id: Task ID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/tracker",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "agent_id": agent_id,
                        "task_id": task_id,
                    },
                    tracker_list_params.TrackerListParams,
                ),
            ),
            cast_to=TrackerListResponse,
        )


class AsyncTrackerResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncTrackerResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTrackerResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTrackerResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/agentex-python#with_streaming_response
        """
        return AsyncTrackerResourceWithStreamingResponse(self)

    async def retrieve(
        self,
        tracker_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentTaskTracker:
        """
        Get agent task tracker by tracker ID

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not tracker_id:
            raise ValueError(f"Expected a non-empty value for `tracker_id` but received {tracker_id!r}")
        return await self._get(
            f"/tracker/{tracker_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentTaskTracker,
        )

    async def update(
        self,
        tracker_id: str,
        *,
        last_processed_event_id: Optional[str] | NotGiven = NOT_GIVEN,
        status: Optional[str] | NotGiven = NOT_GIVEN,
        status_reason: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentTaskTracker:
        """
        Update agent task tracker by tracker ID

        Args:
          last_processed_event_id: The most recent processed event ID (omit to leave unchanged)

          status: Processing status

          status_reason: Optional status reason

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not tracker_id:
            raise ValueError(f"Expected a non-empty value for `tracker_id` but received {tracker_id!r}")
        return await self._put(
            f"/tracker/{tracker_id}",
            body=await async_maybe_transform(
                {
                    "last_processed_event_id": last_processed_event_id,
                    "status": status,
                    "status_reason": status_reason,
                },
                tracker_update_params.TrackerUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentTaskTracker,
        )

    async def list(
        self,
        *,
        agent_id: Optional[str] | NotGiven = NOT_GIVEN,
        task_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> TrackerListResponse:
        """
        List all agent task trackers, optionally filtered by query parameters.

        Args:
          agent_id: Agent ID

          task_id: Task ID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/tracker",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "agent_id": agent_id,
                        "task_id": task_id,
                    },
                    tracker_list_params.TrackerListParams,
                ),
            ),
            cast_to=TrackerListResponse,
        )


class TrackerResourceWithRawResponse:
    def __init__(self, tracker: TrackerResource) -> None:
        self._tracker = tracker

        self.retrieve = to_raw_response_wrapper(
            tracker.retrieve,
        )
        self.update = to_raw_response_wrapper(
            tracker.update,
        )
        self.list = to_raw_response_wrapper(
            tracker.list,
        )


class AsyncTrackerResourceWithRawResponse:
    def __init__(self, tracker: AsyncTrackerResource) -> None:
        self._tracker = tracker

        self.retrieve = async_to_raw_response_wrapper(
            tracker.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            tracker.update,
        )
        self.list = async_to_raw_response_wrapper(
            tracker.list,
        )


class TrackerResourceWithStreamingResponse:
    def __init__(self, tracker: TrackerResource) -> None:
        self._tracker = tracker

        self.retrieve = to_streamed_response_wrapper(
            tracker.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            tracker.update,
        )
        self.list = to_streamed_response_wrapper(
            tracker.list,
        )


class AsyncTrackerResourceWithStreamingResponse:
    def __init__(self, tracker: AsyncTrackerResource) -> None:
        self._tracker = tracker

        self.retrieve = async_to_streamed_response_wrapper(
            tracker.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            tracker.update,
        )
        self.list = async_to_streamed_response_wrapper(
            tracker.list,
        )
