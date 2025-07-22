# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional

import httpx

from ..types import state_list_params, state_create_params, state_update_params
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
from ..types.state import State
from .._base_client import make_request_options
from ..types.state_list_response import StateListResponse

__all__ = ["StatesResource", "AsyncStatesResource"]


class StatesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> StatesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/agentex-python#accessing-raw-response-data-eg-headers
        """
        return StatesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> StatesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/agentex-python#with_streaming_response
        """
        return StatesResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        agent_id: str,
        state: Dict[str, object],
        task_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> State:
        """
        Create Task State

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/states",
            body=maybe_transform(
                {
                    "agent_id": agent_id,
                    "state": state,
                    "task_id": task_id,
                },
                state_create_params.StateCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=State,
        )

    def retrieve(
        self,
        state_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> State:
        """
        Get a state by its unique state ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not state_id:
            raise ValueError(f"Expected a non-empty value for `state_id` but received {state_id!r}")
        return self._get(
            f"/states/{state_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=State,
        )

    def update(
        self,
        state_id: str,
        *,
        agent_id: str,
        state: Dict[str, object],
        task_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> State:
        """
        Update Task State

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not state_id:
            raise ValueError(f"Expected a non-empty value for `state_id` but received {state_id!r}")
        return self._put(
            f"/states/{state_id}",
            body=maybe_transform(
                {
                    "agent_id": agent_id,
                    "state": state,
                    "task_id": task_id,
                },
                state_update_params.StateUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=State,
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
    ) -> StateListResponse:
        """
        List all states, optionally filtered by query parameters.

        Args:
          agent_id: Agent ID

          task_id: Task ID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/states",
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
                    state_list_params.StateListParams,
                ),
            ),
            cast_to=StateListResponse,
        )

    def delete(
        self,
        state_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> State:
        """
        Delete Task State

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not state_id:
            raise ValueError(f"Expected a non-empty value for `state_id` but received {state_id!r}")
        return self._delete(
            f"/states/{state_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=State,
        )


class AsyncStatesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncStatesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncStatesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncStatesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/agentex-python#with_streaming_response
        """
        return AsyncStatesResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        agent_id: str,
        state: Dict[str, object],
        task_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> State:
        """
        Create Task State

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/states",
            body=await async_maybe_transform(
                {
                    "agent_id": agent_id,
                    "state": state,
                    "task_id": task_id,
                },
                state_create_params.StateCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=State,
        )

    async def retrieve(
        self,
        state_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> State:
        """
        Get a state by its unique state ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not state_id:
            raise ValueError(f"Expected a non-empty value for `state_id` but received {state_id!r}")
        return await self._get(
            f"/states/{state_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=State,
        )

    async def update(
        self,
        state_id: str,
        *,
        agent_id: str,
        state: Dict[str, object],
        task_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> State:
        """
        Update Task State

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not state_id:
            raise ValueError(f"Expected a non-empty value for `state_id` but received {state_id!r}")
        return await self._put(
            f"/states/{state_id}",
            body=await async_maybe_transform(
                {
                    "agent_id": agent_id,
                    "state": state,
                    "task_id": task_id,
                },
                state_update_params.StateUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=State,
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
    ) -> StateListResponse:
        """
        List all states, optionally filtered by query parameters.

        Args:
          agent_id: Agent ID

          task_id: Task ID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/states",
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
                    state_list_params.StateListParams,
                ),
            ),
            cast_to=StateListResponse,
        )

    async def delete(
        self,
        state_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> State:
        """
        Delete Task State

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not state_id:
            raise ValueError(f"Expected a non-empty value for `state_id` but received {state_id!r}")
        return await self._delete(
            f"/states/{state_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=State,
        )


class StatesResourceWithRawResponse:
    def __init__(self, states: StatesResource) -> None:
        self._states = states

        self.create = to_raw_response_wrapper(
            states.create,
        )
        self.retrieve = to_raw_response_wrapper(
            states.retrieve,
        )
        self.update = to_raw_response_wrapper(
            states.update,
        )
        self.list = to_raw_response_wrapper(
            states.list,
        )
        self.delete = to_raw_response_wrapper(
            states.delete,
        )


class AsyncStatesResourceWithRawResponse:
    def __init__(self, states: AsyncStatesResource) -> None:
        self._states = states

        self.create = async_to_raw_response_wrapper(
            states.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            states.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            states.update,
        )
        self.list = async_to_raw_response_wrapper(
            states.list,
        )
        self.delete = async_to_raw_response_wrapper(
            states.delete,
        )


class StatesResourceWithStreamingResponse:
    def __init__(self, states: StatesResource) -> None:
        self._states = states

        self.create = to_streamed_response_wrapper(
            states.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            states.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            states.update,
        )
        self.list = to_streamed_response_wrapper(
            states.list,
        )
        self.delete = to_streamed_response_wrapper(
            states.delete,
        )


class AsyncStatesResourceWithStreamingResponse:
    def __init__(self, states: AsyncStatesResource) -> None:
        self._states = states

        self.create = async_to_streamed_response_wrapper(
            states.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            states.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            states.update,
        )
        self.list = async_to_streamed_response_wrapper(
            states.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            states.delete,
        )
