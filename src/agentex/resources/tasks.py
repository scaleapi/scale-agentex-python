# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional
from typing_extensions import Literal

import httpx

from ..types import task_list_params, task_retrieve_params, task_retrieve_by_name_params
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from .._utils import maybe_transform, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._streaming import Stream, AsyncStream
from .._base_client import make_request_options
from ..types.task_list_response import TaskListResponse
from ..types.shared.delete_response import DeleteResponse
from ..types.task_retrieve_response import TaskRetrieveResponse
from ..types.task_retrieve_by_name_response import TaskRetrieveByNameResponse

__all__ = ["TasksResource", "AsyncTasksResource"]


class TasksResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> TasksResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return TasksResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TasksResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return TasksResourceWithStreamingResponse(self)

    def retrieve(
        self,
        task_id: str,
        *,
        relationships: List[Literal["agents"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskRetrieveResponse:
        """
        Get a task by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_id:
            raise ValueError(f"Expected a non-empty value for `task_id` but received {task_id!r}")
        return self._get(
            f"/tasks/{task_id}",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"relationships": relationships}, task_retrieve_params.TaskRetrieveParams),
            ),
            cast_to=TaskRetrieveResponse,
        )

    def list(
        self,
        *,
        agent_id: Optional[str] | Omit = omit,
        agent_name: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        page_number: int | Omit = omit,
        relationships: List[Literal["agents"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskListResponse:
        """
        List all tasks.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/tasks",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "limit": limit,
                        "page_number": page_number,
                        "relationships": relationships,
                    },
                    task_list_params.TaskListParams,
                ),
            ),
            cast_to=TaskListResponse,
        )

    def delete(
        self,
        task_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeleteResponse:
        """
        Delete a task by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_id:
            raise ValueError(f"Expected a non-empty value for `task_id` but received {task_id!r}")
        return self._delete(
            f"/tasks/{task_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    def delete_by_name(
        self,
        task_name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeleteResponse:
        """
        Delete a task by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_name:
            raise ValueError(f"Expected a non-empty value for `task_name` but received {task_name!r}")
        return self._delete(
            f"/tasks/name/{task_name}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    def retrieve_by_name(
        self,
        task_name: str,
        *,
        relationships: List[Literal["agents"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskRetrieveByNameResponse:
        """
        Get a task by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_name:
            raise ValueError(f"Expected a non-empty value for `task_name` but received {task_name!r}")
        return self._get(
            f"/tasks/name/{task_name}",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"relationships": relationships}, task_retrieve_by_name_params.TaskRetrieveByNameParams
                ),
            ),
            cast_to=TaskRetrieveByNameResponse,
        )

    def stream_events(
        self,
        task_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Stream[object]:
        """
        Stream events for a task by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_id:
            raise ValueError(f"Expected a non-empty value for `task_id` but received {task_id!r}")
        return self._get(
            f"/tasks/{task_id}/stream",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
            stream=True,
            stream_cls=Stream[object],
        )

    def stream_events_by_name(
        self,
        task_name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Stream[object]:
        """
        Stream events for a task by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_name:
            raise ValueError(f"Expected a non-empty value for `task_name` but received {task_name!r}")
        return self._get(
            f"/tasks/name/{task_name}/stream",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
            stream=True,
            stream_cls=Stream[object],
        )


class AsyncTasksResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncTasksResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTasksResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTasksResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return AsyncTasksResourceWithStreamingResponse(self)

    async def retrieve(
        self,
        task_id: str,
        *,
        relationships: List[Literal["agents"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskRetrieveResponse:
        """
        Get a task by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_id:
            raise ValueError(f"Expected a non-empty value for `task_id` but received {task_id!r}")
        return await self._get(
            f"/tasks/{task_id}",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"relationships": relationships}, task_retrieve_params.TaskRetrieveParams
                ),
            ),
            cast_to=TaskRetrieveResponse,
        )

    async def list(
        self,
        *,
        agent_id: Optional[str] | Omit = omit,
        agent_name: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        page_number: int | Omit = omit,
        relationships: List[Literal["agents"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskListResponse:
        """
        List all tasks.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/tasks",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                        "limit": limit,
                        "page_number": page_number,
                        "relationships": relationships,
                    },
                    task_list_params.TaskListParams,
                ),
            ),
            cast_to=TaskListResponse,
        )

    async def delete(
        self,
        task_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeleteResponse:
        """
        Delete a task by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_id:
            raise ValueError(f"Expected a non-empty value for `task_id` but received {task_id!r}")
        return await self._delete(
            f"/tasks/{task_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    async def delete_by_name(
        self,
        task_name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeleteResponse:
        """
        Delete a task by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_name:
            raise ValueError(f"Expected a non-empty value for `task_name` but received {task_name!r}")
        return await self._delete(
            f"/tasks/name/{task_name}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    async def retrieve_by_name(
        self,
        task_name: str,
        *,
        relationships: List[Literal["agents"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskRetrieveByNameResponse:
        """
        Get a task by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_name:
            raise ValueError(f"Expected a non-empty value for `task_name` but received {task_name!r}")
        return await self._get(
            f"/tasks/name/{task_name}",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"relationships": relationships}, task_retrieve_by_name_params.TaskRetrieveByNameParams
                ),
            ),
            cast_to=TaskRetrieveByNameResponse,
        )

    async def stream_events(
        self,
        task_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncStream[object]:
        """
        Stream events for a task by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_id:
            raise ValueError(f"Expected a non-empty value for `task_id` but received {task_id!r}")
        return await self._get(
            f"/tasks/{task_id}/stream",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
            stream=True,
            stream_cls=AsyncStream[object],
        )

    async def stream_events_by_name(
        self,
        task_name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncStream[object]:
        """
        Stream events for a task by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not task_name:
            raise ValueError(f"Expected a non-empty value for `task_name` but received {task_name!r}")
        return await self._get(
            f"/tasks/name/{task_name}/stream",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
            stream=True,
            stream_cls=AsyncStream[object],
        )


class TasksResourceWithRawResponse:
    def __init__(self, tasks: TasksResource) -> None:
        self._tasks = tasks

        self.retrieve = to_raw_response_wrapper(
            tasks.retrieve,
        )
        self.list = to_raw_response_wrapper(
            tasks.list,
        )
        self.delete = to_raw_response_wrapper(
            tasks.delete,
        )
        self.delete_by_name = to_raw_response_wrapper(
            tasks.delete_by_name,
        )
        self.retrieve_by_name = to_raw_response_wrapper(
            tasks.retrieve_by_name,
        )
        self.stream_events = to_raw_response_wrapper(
            tasks.stream_events,
        )
        self.stream_events_by_name = to_raw_response_wrapper(
            tasks.stream_events_by_name,
        )


class AsyncTasksResourceWithRawResponse:
    def __init__(self, tasks: AsyncTasksResource) -> None:
        self._tasks = tasks

        self.retrieve = async_to_raw_response_wrapper(
            tasks.retrieve,
        )
        self.list = async_to_raw_response_wrapper(
            tasks.list,
        )
        self.delete = async_to_raw_response_wrapper(
            tasks.delete,
        )
        self.delete_by_name = async_to_raw_response_wrapper(
            tasks.delete_by_name,
        )
        self.retrieve_by_name = async_to_raw_response_wrapper(
            tasks.retrieve_by_name,
        )
        self.stream_events = async_to_raw_response_wrapper(
            tasks.stream_events,
        )
        self.stream_events_by_name = async_to_raw_response_wrapper(
            tasks.stream_events_by_name,
        )


class TasksResourceWithStreamingResponse:
    def __init__(self, tasks: TasksResource) -> None:
        self._tasks = tasks

        self.retrieve = to_streamed_response_wrapper(
            tasks.retrieve,
        )
        self.list = to_streamed_response_wrapper(
            tasks.list,
        )
        self.delete = to_streamed_response_wrapper(
            tasks.delete,
        )
        self.delete_by_name = to_streamed_response_wrapper(
            tasks.delete_by_name,
        )
        self.retrieve_by_name = to_streamed_response_wrapper(
            tasks.retrieve_by_name,
        )
        self.stream_events = to_streamed_response_wrapper(
            tasks.stream_events,
        )
        self.stream_events_by_name = to_streamed_response_wrapper(
            tasks.stream_events_by_name,
        )


class AsyncTasksResourceWithStreamingResponse:
    def __init__(self, tasks: AsyncTasksResource) -> None:
        self._tasks = tasks

        self.retrieve = async_to_streamed_response_wrapper(
            tasks.retrieve,
        )
        self.list = async_to_streamed_response_wrapper(
            tasks.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            tasks.delete,
        )
        self.delete_by_name = async_to_streamed_response_wrapper(
            tasks.delete_by_name,
        )
        self.retrieve_by_name = async_to_streamed_response_wrapper(
            tasks.retrieve_by_name,
        )
        self.stream_events = async_to_streamed_response_wrapper(
            tasks.stream_events,
        )
        self.stream_events_by_name = async_to_streamed_response_wrapper(
            tasks.stream_events_by_name,
        )
