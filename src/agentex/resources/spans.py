# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime

import httpx

from ..types import span_list_params, span_create_params, span_update_params
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
from ..types.span import Span
from .._base_client import make_request_options
from ..types.span_list_response import SpanListResponse

__all__ = ["SpansResource", "AsyncSpansResource"]


class SpansResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> SpansResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/agentex-python#accessing-raw-response-data-eg-headers
        """
        return SpansResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SpansResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/agentex-python#with_streaming_response
        """
        return SpansResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        name: str,
        start_time: Union[str, datetime],
        trace_id: str,
        id: Optional[str] | NotGiven = NOT_GIVEN,
        data: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        end_time: Union[str, datetime, None] | NotGiven = NOT_GIVEN,
        input: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        output: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        parent_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Span:
        """
        Create a new span with the provided parameters

        Args:
          name: Name that describes what operation this span represents

          start_time: The time the span started

          trace_id: Unique identifier for the trace this span belongs to

          id: Unique identifier for the span. If not provided, an ID will be generated.

          data: Any additional metadata or context for the span

          end_time: The time the span ended

          input: Input parameters or data for the operation

          output: Output data resulting from the operation

          parent_id: ID of the parent span if this is a child span in a trace

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/spans",
            body=maybe_transform(
                {
                    "name": name,
                    "start_time": start_time,
                    "trace_id": trace_id,
                    "id": id,
                    "data": data,
                    "end_time": end_time,
                    "input": input,
                    "output": output,
                    "parent_id": parent_id,
                },
                span_create_params.SpanCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Span,
        )

    def retrieve(
        self,
        span_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Span:
        """
        Get a span by ID

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not span_id:
            raise ValueError(f"Expected a non-empty value for `span_id` but received {span_id!r}")
        return self._get(
            f"/spans/{span_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Span,
        )

    def update(
        self,
        span_id: str,
        *,
        data: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        end_time: Union[str, datetime, None] | NotGiven = NOT_GIVEN,
        input: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        name: Optional[str] | NotGiven = NOT_GIVEN,
        output: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        parent_id: Optional[str] | NotGiven = NOT_GIVEN,
        start_time: Union[str, datetime, None] | NotGiven = NOT_GIVEN,
        trace_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Span:
        """
        Update a span with the provided output data and mark it as complete

        Args:
          data: Any additional metadata or context for the span

          end_time: The time the span ended

          input: Input parameters or data for the operation

          name: Name that describes what operation this span represents

          output: Output data resulting from the operation

          parent_id: ID of the parent span if this is a child span in a trace

          start_time: The time the span started

          trace_id: Unique identifier for the trace this span belongs to

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not span_id:
            raise ValueError(f"Expected a non-empty value for `span_id` but received {span_id!r}")
        return self._patch(
            f"/spans/{span_id}",
            body=maybe_transform(
                {
                    "data": data,
                    "end_time": end_time,
                    "input": input,
                    "name": name,
                    "output": output,
                    "parent_id": parent_id,
                    "start_time": start_time,
                    "trace_id": trace_id,
                },
                span_update_params.SpanUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Span,
        )

    def list(
        self,
        *,
        trace_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> SpanListResponse:
        """
        List all spans for a given trace ID

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/spans",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"trace_id": trace_id}, span_list_params.SpanListParams),
            ),
            cast_to=SpanListResponse,
        )


class AsyncSpansResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncSpansResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncSpansResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSpansResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/agentex-python#with_streaming_response
        """
        return AsyncSpansResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        name: str,
        start_time: Union[str, datetime],
        trace_id: str,
        id: Optional[str] | NotGiven = NOT_GIVEN,
        data: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        end_time: Union[str, datetime, None] | NotGiven = NOT_GIVEN,
        input: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        output: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        parent_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Span:
        """
        Create a new span with the provided parameters

        Args:
          name: Name that describes what operation this span represents

          start_time: The time the span started

          trace_id: Unique identifier for the trace this span belongs to

          id: Unique identifier for the span. If not provided, an ID will be generated.

          data: Any additional metadata or context for the span

          end_time: The time the span ended

          input: Input parameters or data for the operation

          output: Output data resulting from the operation

          parent_id: ID of the parent span if this is a child span in a trace

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/spans",
            body=await async_maybe_transform(
                {
                    "name": name,
                    "start_time": start_time,
                    "trace_id": trace_id,
                    "id": id,
                    "data": data,
                    "end_time": end_time,
                    "input": input,
                    "output": output,
                    "parent_id": parent_id,
                },
                span_create_params.SpanCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Span,
        )

    async def retrieve(
        self,
        span_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Span:
        """
        Get a span by ID

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not span_id:
            raise ValueError(f"Expected a non-empty value for `span_id` but received {span_id!r}")
        return await self._get(
            f"/spans/{span_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Span,
        )

    async def update(
        self,
        span_id: str,
        *,
        data: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        end_time: Union[str, datetime, None] | NotGiven = NOT_GIVEN,
        input: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        name: Optional[str] | NotGiven = NOT_GIVEN,
        output: Union[Dict[str, object], Iterable[Dict[str, object]], None] | NotGiven = NOT_GIVEN,
        parent_id: Optional[str] | NotGiven = NOT_GIVEN,
        start_time: Union[str, datetime, None] | NotGiven = NOT_GIVEN,
        trace_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Span:
        """
        Update a span with the provided output data and mark it as complete

        Args:
          data: Any additional metadata or context for the span

          end_time: The time the span ended

          input: Input parameters or data for the operation

          name: Name that describes what operation this span represents

          output: Output data resulting from the operation

          parent_id: ID of the parent span if this is a child span in a trace

          start_time: The time the span started

          trace_id: Unique identifier for the trace this span belongs to

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not span_id:
            raise ValueError(f"Expected a non-empty value for `span_id` but received {span_id!r}")
        return await self._patch(
            f"/spans/{span_id}",
            body=await async_maybe_transform(
                {
                    "data": data,
                    "end_time": end_time,
                    "input": input,
                    "name": name,
                    "output": output,
                    "parent_id": parent_id,
                    "start_time": start_time,
                    "trace_id": trace_id,
                },
                span_update_params.SpanUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Span,
        )

    async def list(
        self,
        *,
        trace_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> SpanListResponse:
        """
        List all spans for a given trace ID

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/spans",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"trace_id": trace_id}, span_list_params.SpanListParams),
            ),
            cast_to=SpanListResponse,
        )


class SpansResourceWithRawResponse:
    def __init__(self, spans: SpansResource) -> None:
        self._spans = spans

        self.create = to_raw_response_wrapper(
            spans.create,
        )
        self.retrieve = to_raw_response_wrapper(
            spans.retrieve,
        )
        self.update = to_raw_response_wrapper(
            spans.update,
        )
        self.list = to_raw_response_wrapper(
            spans.list,
        )


class AsyncSpansResourceWithRawResponse:
    def __init__(self, spans: AsyncSpansResource) -> None:
        self._spans = spans

        self.create = async_to_raw_response_wrapper(
            spans.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            spans.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            spans.update,
        )
        self.list = async_to_raw_response_wrapper(
            spans.list,
        )


class SpansResourceWithStreamingResponse:
    def __init__(self, spans: SpansResource) -> None:
        self._spans = spans

        self.create = to_streamed_response_wrapper(
            spans.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            spans.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            spans.update,
        )
        self.list = to_streamed_response_wrapper(
            spans.list,
        )


class AsyncSpansResourceWithStreamingResponse:
    def __init__(self, spans: AsyncSpansResource) -> None:
        self._spans = spans

        self.create = async_to_streamed_response_wrapper(
            spans.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            spans.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            spans.update,
        )
        self.list = async_to_streamed_response_wrapper(
            spans.list,
        )
