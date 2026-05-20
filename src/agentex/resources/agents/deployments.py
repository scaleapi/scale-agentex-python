# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from typing_extensions import Literal

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
from ...types.agents import deployment_list_params, deployment_create_params, deployment_preview_rpc_params
from ...types.agent_rpc_response import AgentRpcResponse
from ...types.shared.delete_response import DeleteResponse
from ...types.agents.deployment_list_response import DeploymentListResponse
from ...types.agents.deployment_create_response import DeploymentCreateResponse
from ...types.agents.deployment_promote_response import DeploymentPromoteResponse
from ...types.agents.deployment_retrieve_response import DeploymentRetrieveResponse

__all__ = ["DeploymentsResource", "AsyncDeploymentsResource"]


class DeploymentsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> DeploymentsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return DeploymentsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> DeploymentsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return DeploymentsResourceWithStreamingResponse(self)

    def create(
        self,
        agent_id: str,
        *,
        docker_image: str,
        helm_release_name: Optional[str] | Omit = omit,
        registration_metadata: Optional[Dict[str, object]] | Omit = omit,
        sgp_deploy_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentCreateResponse:
        """
        Create a new deployment record in PENDING status.

        Args:
          docker_image: Full Docker image URI.

          helm_release_name: Helm release name.

          registration_metadata: Git/build metadata (commit_hash, branch_name, author_name, author_email,
              build_timestamp).

          sgp_deploy_id: SGP deployment ID.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return self._post(
            path_template("/agents/{agent_id}/deployments", agent_id=agent_id),
            body=maybe_transform(
                {
                    "docker_image": docker_image,
                    "helm_release_name": helm_release_name,
                    "registration_metadata": registration_metadata,
                    "sgp_deploy_id": sgp_deploy_id,
                },
                deployment_create_params.DeploymentCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeploymentCreateResponse,
        )

    def retrieve(
        self,
        deployment_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentRetrieveResponse:
        """
        Get a specific deployment by ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return self._get(
            path_template(
                "/agents/{agent_id}/deployments/{deployment_id}", agent_id=agent_id, deployment_id=deployment_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeploymentRetrieveResponse,
        )

    def list(
        self,
        agent_id: str,
        *,
        limit: int | Omit = omit,
        order_by: Optional[str] | Omit = omit,
        order_direction: str | Omit = omit,
        page_number: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentListResponse:
        """
        List deployments for an agent, newest first.

        Args:
          limit: Limit

          order_by: Field to order by

          order_direction: Order direction (asc or desc)

          page_number: Page number

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return self._get(
            path_template("/agents/{agent_id}/deployments", agent_id=agent_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "limit": limit,
                        "order_by": order_by,
                        "order_direction": order_direction,
                        "page_number": page_number,
                    },
                    deployment_list_params.DeploymentListParams,
                ),
            ),
            cast_to=DeploymentListResponse,
        )

    def delete(
        self,
        deployment_id: str,
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
        Delete a non-production deployment.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return self._delete(
            path_template(
                "/agents/{agent_id}/deployments/{deployment_id}", agent_id=agent_id, deployment_id=deployment_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    def preview_rpc(
        self,
        deployment_id: str,
        *,
        agent_id: str,
        method: Literal["event/send", "task/create", "message/send", "task/cancel"],
        params: deployment_preview_rpc_params.Params,
        id: Union[int, str, None] | Omit = omit,
        jsonrpc: Literal["2.0"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AgentRpcResponse:
        """
        Send an RPC request to a specific deployment (for preview testing).

        Args:
          params: The parameters for the agent RPC request

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return self._post(
            path_template(
                "/agents/{agent_id}/deployments/{deployment_id}/rpc", agent_id=agent_id, deployment_id=deployment_id
            ),
            body=maybe_transform(
                {
                    "method": method,
                    "params": params,
                    "id": id,
                    "jsonrpc": jsonrpc,
                },
                deployment_preview_rpc_params.DeploymentPreviewRpcParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentRpcResponse,
        )

    def promote(
        self,
        deployment_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentPromoteResponse:
        """
        Promote a deployment to production with atomic cutover.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return self._post(
            path_template(
                "/agents/{agent_id}/deployments/{deployment_id}/promote", agent_id=agent_id, deployment_id=deployment_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeploymentPromoteResponse,
        )


class AsyncDeploymentsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncDeploymentsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncDeploymentsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncDeploymentsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return AsyncDeploymentsResourceWithStreamingResponse(self)

    async def create(
        self,
        agent_id: str,
        *,
        docker_image: str,
        helm_release_name: Optional[str] | Omit = omit,
        registration_metadata: Optional[Dict[str, object]] | Omit = omit,
        sgp_deploy_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentCreateResponse:
        """
        Create a new deployment record in PENDING status.

        Args:
          docker_image: Full Docker image URI.

          helm_release_name: Helm release name.

          registration_metadata: Git/build metadata (commit_hash, branch_name, author_name, author_email,
              build_timestamp).

          sgp_deploy_id: SGP deployment ID.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return await self._post(
            path_template("/agents/{agent_id}/deployments", agent_id=agent_id),
            body=await async_maybe_transform(
                {
                    "docker_image": docker_image,
                    "helm_release_name": helm_release_name,
                    "registration_metadata": registration_metadata,
                    "sgp_deploy_id": sgp_deploy_id,
                },
                deployment_create_params.DeploymentCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeploymentCreateResponse,
        )

    async def retrieve(
        self,
        deployment_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentRetrieveResponse:
        """
        Get a specific deployment by ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return await self._get(
            path_template(
                "/agents/{agent_id}/deployments/{deployment_id}", agent_id=agent_id, deployment_id=deployment_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeploymentRetrieveResponse,
        )

    async def list(
        self,
        agent_id: str,
        *,
        limit: int | Omit = omit,
        order_by: Optional[str] | Omit = omit,
        order_direction: str | Omit = omit,
        page_number: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentListResponse:
        """
        List deployments for an agent, newest first.

        Args:
          limit: Limit

          order_by: Field to order by

          order_direction: Order direction (asc or desc)

          page_number: Page number

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return await self._get(
            path_template("/agents/{agent_id}/deployments", agent_id=agent_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "limit": limit,
                        "order_by": order_by,
                        "order_direction": order_direction,
                        "page_number": page_number,
                    },
                    deployment_list_params.DeploymentListParams,
                ),
            ),
            cast_to=DeploymentListResponse,
        )

    async def delete(
        self,
        deployment_id: str,
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
        Delete a non-production deployment.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return await self._delete(
            path_template(
                "/agents/{agent_id}/deployments/{deployment_id}", agent_id=agent_id, deployment_id=deployment_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    async def preview_rpc(
        self,
        deployment_id: str,
        *,
        agent_id: str,
        method: Literal["event/send", "task/create", "message/send", "task/cancel"],
        params: deployment_preview_rpc_params.Params,
        id: Union[int, str, None] | Omit = omit,
        jsonrpc: Literal["2.0"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AgentRpcResponse:
        """
        Send an RPC request to a specific deployment (for preview testing).

        Args:
          params: The parameters for the agent RPC request

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return await self._post(
            path_template(
                "/agents/{agent_id}/deployments/{deployment_id}/rpc", agent_id=agent_id, deployment_id=deployment_id
            ),
            body=await async_maybe_transform(
                {
                    "method": method,
                    "params": params,
                    "id": id,
                    "jsonrpc": jsonrpc,
                },
                deployment_preview_rpc_params.DeploymentPreviewRpcParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentRpcResponse,
        )

    async def promote(
        self,
        deployment_id: str,
        *,
        agent_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DeploymentPromoteResponse:
        """
        Promote a deployment to production with atomic cutover.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        if not deployment_id:
            raise ValueError(f"Expected a non-empty value for `deployment_id` but received {deployment_id!r}")
        return await self._post(
            path_template(
                "/agents/{agent_id}/deployments/{deployment_id}/promote", agent_id=agent_id, deployment_id=deployment_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeploymentPromoteResponse,
        )


class DeploymentsResourceWithRawResponse:
    def __init__(self, deployments: DeploymentsResource) -> None:
        self._deployments = deployments

        self.create = to_raw_response_wrapper(
            deployments.create,
        )
        self.retrieve = to_raw_response_wrapper(
            deployments.retrieve,
        )
        self.list = to_raw_response_wrapper(
            deployments.list,
        )
        self.delete = to_raw_response_wrapper(
            deployments.delete,
        )
        self.preview_rpc = to_raw_response_wrapper(
            deployments.preview_rpc,
        )
        self.promote = to_raw_response_wrapper(
            deployments.promote,
        )


class AsyncDeploymentsResourceWithRawResponse:
    def __init__(self, deployments: AsyncDeploymentsResource) -> None:
        self._deployments = deployments

        self.create = async_to_raw_response_wrapper(
            deployments.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            deployments.retrieve,
        )
        self.list = async_to_raw_response_wrapper(
            deployments.list,
        )
        self.delete = async_to_raw_response_wrapper(
            deployments.delete,
        )
        self.preview_rpc = async_to_raw_response_wrapper(
            deployments.preview_rpc,
        )
        self.promote = async_to_raw_response_wrapper(
            deployments.promote,
        )


class DeploymentsResourceWithStreamingResponse:
    def __init__(self, deployments: DeploymentsResource) -> None:
        self._deployments = deployments

        self.create = to_streamed_response_wrapper(
            deployments.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            deployments.retrieve,
        )
        self.list = to_streamed_response_wrapper(
            deployments.list,
        )
        self.delete = to_streamed_response_wrapper(
            deployments.delete,
        )
        self.preview_rpc = to_streamed_response_wrapper(
            deployments.preview_rpc,
        )
        self.promote = to_streamed_response_wrapper(
            deployments.promote,
        )


class AsyncDeploymentsResourceWithStreamingResponse:
    def __init__(self, deployments: AsyncDeploymentsResource) -> None:
        self._deployments = deployments

        self.create = async_to_streamed_response_wrapper(
            deployments.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            deployments.retrieve,
        )
        self.list = async_to_streamed_response_wrapper(
            deployments.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            deployments.delete,
        )
        self.preview_rpc = async_to_streamed_response_wrapper(
            deployments.preview_rpc,
        )
        self.promote = async_to_streamed_response_wrapper(
            deployments.promote,
        )
