# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

import httpx

from ..types import deployment_history_list_params
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
from .._base_client import make_request_options
from ..types.deployment_history import DeploymentHistory
from ..types.deployment_history_list_response import DeploymentHistoryListResponse

__all__ = ["DeploymentHistoryResource", "AsyncDeploymentHistoryResource"]


class DeploymentHistoryResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> DeploymentHistoryResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return DeploymentHistoryResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> DeploymentHistoryResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return DeploymentHistoryResourceWithStreamingResponse(self)

    def retrieve(
        self,
        deployment_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentHistory:
        """
        Get a deployment record by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return self._get(
            f"/deployment-history/{deployment_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeploymentHistory,
        )

    def list(
        self,
        *,
        agent_id: Optional[str] | Omit = omit,
        agent_name: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        page_number: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentHistoryListResponse:
        """
        List deployment history for an agent.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/deployment-history",
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
                    },
                    deployment_history_list_params.DeploymentHistoryListParams,
                ),
            ),
            cast_to=DeploymentHistoryListResponse,
        )


class AsyncDeploymentHistoryResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncDeploymentHistoryResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncDeploymentHistoryResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncDeploymentHistoryResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return AsyncDeploymentHistoryResourceWithStreamingResponse(self)

    async def retrieve(
        self,
        deployment_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentHistory:
        """
        Get a deployment record by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return await self._get(
            f"/deployment-history/{deployment_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeploymentHistory,
        )

    async def list(
        self,
        *,
        agent_id: Optional[str] | Omit = omit,
        agent_name: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        page_number: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentHistoryListResponse:
        """
        List deployment history for an agent.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/deployment-history",
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
                    },
                    deployment_history_list_params.DeploymentHistoryListParams,
                ),
            ),
            cast_to=DeploymentHistoryListResponse,
        )


class DeploymentHistoryResourceWithRawResponse:
    def __init__(self, deployment_history: DeploymentHistoryResource) -> None:
        self._deployment_history = deployment_history

        self.retrieve = to_raw_response_wrapper(
            deployment_history.retrieve,
        )
        self.list = to_raw_response_wrapper(
            deployment_history.list,
        )


class AsyncDeploymentHistoryResourceWithRawResponse:
    def __init__(self, deployment_history: AsyncDeploymentHistoryResource) -> None:
        self._deployment_history = deployment_history

        self.retrieve = async_to_raw_response_wrapper(
            deployment_history.retrieve,
        )
        self.list = async_to_raw_response_wrapper(
            deployment_history.list,
        )


class DeploymentHistoryResourceWithStreamingResponse:
    def __init__(self, deployment_history: DeploymentHistoryResource) -> None:
        self._deployment_history = deployment_history

        self.retrieve = to_streamed_response_wrapper(
            deployment_history.retrieve,
        )
        self.list = to_streamed_response_wrapper(
            deployment_history.list,
        )


class AsyncDeploymentHistoryResourceWithStreamingResponse:
    def __init__(self, deployment_history: AsyncDeploymentHistoryResource) -> None:
        self._deployment_history = deployment_history

        self.retrieve = async_to_streamed_response_wrapper(
            deployment_history.retrieve,
        )
        self.list = async_to_streamed_response_wrapper(
            deployment_history.list,
        )
