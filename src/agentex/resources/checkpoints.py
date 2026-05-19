# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional

import httpx

from ..types import (
    checkpoint_put_params,
    checkpoint_list_params,
    checkpoint_get_tuple_params,
    checkpoint_put_writes_params,
    checkpoint_delete_thread_params,
)
from .._types import Body, Omit, Query, Headers, NoneType, NotGiven, omit, not_given
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
from ..types.checkpoint_put_response import CheckpointPutResponse
from ..types.checkpoint_list_response import CheckpointListResponse
from ..types.checkpoint_get_tuple_response import CheckpointGetTupleResponse

__all__ = ["CheckpointsResource", "AsyncCheckpointsResource"]


class CheckpointsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> CheckpointsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return CheckpointsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> CheckpointsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return CheckpointsResourceWithStreamingResponse(self)

    def list(
        self,
        *,
        thread_id: str,
        before_checkpoint_id: Optional[str] | Omit = omit,
        checkpoint_ns: Optional[str] | Omit = omit,
        filter_metadata: Optional[Dict[str, object]] | Omit = omit,
        limit: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CheckpointListResponse:
        """
        List Checkpoints

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/checkpoints/list",
            body=maybe_transform(
                {
                    "thread_id": thread_id,
                    "before_checkpoint_id": before_checkpoint_id,
                    "checkpoint_ns": checkpoint_ns,
                    "filter_metadata": filter_metadata,
                    "limit": limit,
                },
                checkpoint_list_params.CheckpointListParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CheckpointListResponse,
        )

    def delete_thread(
        self,
        *,
        thread_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """
        Delete Thread

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._post(
            "/checkpoints/delete-thread",
            body=maybe_transform(
                {"thread_id": thread_id}, checkpoint_delete_thread_params.CheckpointDeleteThreadParams
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )

    def get_tuple(
        self,
        *,
        thread_id: str,
        checkpoint_id: Optional[str] | Omit = omit,
        checkpoint_ns: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Optional[CheckpointGetTupleResponse]:
        """
        Get Checkpoint Tuple

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/checkpoints/get-tuple",
            body=maybe_transform(
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_ns": checkpoint_ns,
                },
                checkpoint_get_tuple_params.CheckpointGetTupleParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CheckpointGetTupleResponse,
        )

    def put(
        self,
        *,
        checkpoint: Dict[str, object],
        checkpoint_id: str,
        thread_id: str,
        blobs: Iterable[checkpoint_put_params.Blob] | Omit = omit,
        checkpoint_ns: str | Omit = omit,
        metadata: Dict[str, object] | Omit = omit,
        parent_checkpoint_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CheckpointPutResponse:
        """
        Put Checkpoint

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/checkpoints/put",
            body=maybe_transform(
                {
                    "checkpoint": checkpoint,
                    "checkpoint_id": checkpoint_id,
                    "thread_id": thread_id,
                    "blobs": blobs,
                    "checkpoint_ns": checkpoint_ns,
                    "metadata": metadata,
                    "parent_checkpoint_id": parent_checkpoint_id,
                },
                checkpoint_put_params.CheckpointPutParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CheckpointPutResponse,
        )

    def put_writes(
        self,
        *,
        checkpoint_id: str,
        thread_id: str,
        writes: Iterable[checkpoint_put_writes_params.Write],
        checkpoint_ns: str | Omit = omit,
        upsert: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """
        Put Writes

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._post(
            "/checkpoints/put-writes",
            body=maybe_transform(
                {
                    "checkpoint_id": checkpoint_id,
                    "thread_id": thread_id,
                    "writes": writes,
                    "checkpoint_ns": checkpoint_ns,
                    "upsert": upsert,
                },
                checkpoint_put_writes_params.CheckpointPutWritesParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class AsyncCheckpointsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncCheckpointsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncCheckpointsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncCheckpointsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return AsyncCheckpointsResourceWithStreamingResponse(self)

    async def list(
        self,
        *,
        thread_id: str,
        before_checkpoint_id: Optional[str] | Omit = omit,
        checkpoint_ns: Optional[str] | Omit = omit,
        filter_metadata: Optional[Dict[str, object]] | Omit = omit,
        limit: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CheckpointListResponse:
        """
        List Checkpoints

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/checkpoints/list",
            body=await async_maybe_transform(
                {
                    "thread_id": thread_id,
                    "before_checkpoint_id": before_checkpoint_id,
                    "checkpoint_ns": checkpoint_ns,
                    "filter_metadata": filter_metadata,
                    "limit": limit,
                },
                checkpoint_list_params.CheckpointListParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CheckpointListResponse,
        )

    async def delete_thread(
        self,
        *,
        thread_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """
        Delete Thread

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._post(
            "/checkpoints/delete-thread",
            body=await async_maybe_transform(
                {"thread_id": thread_id}, checkpoint_delete_thread_params.CheckpointDeleteThreadParams
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )

    async def get_tuple(
        self,
        *,
        thread_id: str,
        checkpoint_id: Optional[str] | Omit = omit,
        checkpoint_ns: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Optional[CheckpointGetTupleResponse]:
        """
        Get Checkpoint Tuple

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/checkpoints/get-tuple",
            body=await async_maybe_transform(
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_ns": checkpoint_ns,
                },
                checkpoint_get_tuple_params.CheckpointGetTupleParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CheckpointGetTupleResponse,
        )

    async def put(
        self,
        *,
        checkpoint: Dict[str, object],
        checkpoint_id: str,
        thread_id: str,
        blobs: Iterable[checkpoint_put_params.Blob] | Omit = omit,
        checkpoint_ns: str | Omit = omit,
        metadata: Dict[str, object] | Omit = omit,
        parent_checkpoint_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CheckpointPutResponse:
        """
        Put Checkpoint

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/checkpoints/put",
            body=await async_maybe_transform(
                {
                    "checkpoint": checkpoint,
                    "checkpoint_id": checkpoint_id,
                    "thread_id": thread_id,
                    "blobs": blobs,
                    "checkpoint_ns": checkpoint_ns,
                    "metadata": metadata,
                    "parent_checkpoint_id": parent_checkpoint_id,
                },
                checkpoint_put_params.CheckpointPutParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CheckpointPutResponse,
        )

    async def put_writes(
        self,
        *,
        checkpoint_id: str,
        thread_id: str,
        writes: Iterable[checkpoint_put_writes_params.Write],
        checkpoint_ns: str | Omit = omit,
        upsert: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """
        Put Writes

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._post(
            "/checkpoints/put-writes",
            body=await async_maybe_transform(
                {
                    "checkpoint_id": checkpoint_id,
                    "thread_id": thread_id,
                    "writes": writes,
                    "checkpoint_ns": checkpoint_ns,
                    "upsert": upsert,
                },
                checkpoint_put_writes_params.CheckpointPutWritesParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class CheckpointsResourceWithRawResponse:
    def __init__(self, checkpoints: CheckpointsResource) -> None:
        self._checkpoints = checkpoints

        self.list = to_raw_response_wrapper(
            checkpoints.list,
        )
        self.delete_thread = to_raw_response_wrapper(
            checkpoints.delete_thread,
        )
        self.get_tuple = to_raw_response_wrapper(
            checkpoints.get_tuple,
        )
        self.put = to_raw_response_wrapper(
            checkpoints.put,
        )
        self.put_writes = to_raw_response_wrapper(
            checkpoints.put_writes,
        )


class AsyncCheckpointsResourceWithRawResponse:
    def __init__(self, checkpoints: AsyncCheckpointsResource) -> None:
        self._checkpoints = checkpoints

        self.list = async_to_raw_response_wrapper(
            checkpoints.list,
        )
        self.delete_thread = async_to_raw_response_wrapper(
            checkpoints.delete_thread,
        )
        self.get_tuple = async_to_raw_response_wrapper(
            checkpoints.get_tuple,
        )
        self.put = async_to_raw_response_wrapper(
            checkpoints.put,
        )
        self.put_writes = async_to_raw_response_wrapper(
            checkpoints.put_writes,
        )


class CheckpointsResourceWithStreamingResponse:
    def __init__(self, checkpoints: CheckpointsResource) -> None:
        self._checkpoints = checkpoints

        self.list = to_streamed_response_wrapper(
            checkpoints.list,
        )
        self.delete_thread = to_streamed_response_wrapper(
            checkpoints.delete_thread,
        )
        self.get_tuple = to_streamed_response_wrapper(
            checkpoints.get_tuple,
        )
        self.put = to_streamed_response_wrapper(
            checkpoints.put,
        )
        self.put_writes = to_streamed_response_wrapper(
            checkpoints.put_writes,
        )


class AsyncCheckpointsResourceWithStreamingResponse:
    def __init__(self, checkpoints: AsyncCheckpointsResource) -> None:
        self._checkpoints = checkpoints

        self.list = async_to_streamed_response_wrapper(
            checkpoints.list,
        )
        self.delete_thread = async_to_streamed_response_wrapper(
            checkpoints.delete_thread,
        )
        self.get_tuple = async_to_streamed_response_wrapper(
            checkpoints.get_tuple,
        )
        self.put = async_to_streamed_response_wrapper(
            checkpoints.put,
        )
        self.put_writes = async_to_streamed_response_wrapper(
            checkpoints.put_writes,
        )
