# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import json
from typing import AsyncGenerator, Generator, Union, Optional
from typing_extensions import Literal

import httpx

from ..types import agent_rpc_params, agent_list_params, agent_rpc_by_name_params
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
from ..types.agent import Agent
from .._base_client import make_request_options
from ..types.agent_rpc_response import AgentRpcResponse, CancelTaskResponse, CreateTaskResponse, SendEventResponse, SendMessageResponse, SendMessageStreamResponse
from ..types.agent_list_response import AgentListResponse
from ..types.shared.delete_response import DeleteResponse

__all__ = ["AgentsResource", "AsyncAgentsResource"]


class AgentsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AgentsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/agentex-python#accessing-raw-response-data-eg-headers
        """
        return AgentsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AgentsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/agentex-python#with_streaming_response
        """
        return AgentsResourceWithStreamingResponse(self)

    def retrieve(
        self,
        agent_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Agent:
        """
        Get an agent by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return self._get(
            f"/agents/{agent_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Agent,
        )

    def list(
        self,
        *,
        task_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentListResponse:
        """
        List all registered agents, optionally filtered by query parameters.

        Args:
          task_id: Task ID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/agents",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"task_id": task_id}, agent_list_params.AgentListParams),
            ),
            cast_to=AgentListResponse,
        )

    def delete(
        self,
        agent_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> DeleteResponse:
        """
        Delete an agent by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return self._delete(
            f"/agents/{agent_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    def delete_by_name(
        self,
        agent_name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> DeleteResponse:
        """
        Delete an agent by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_name:
            raise ValueError(f"Expected a non-empty value for `agent_name` but received {agent_name!r}")
        return self._delete(
            f"/agents/name/{agent_name}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    def retrieve_by_name(
        self,
        agent_name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Agent:
        """
        Get an agent by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_name:
            raise ValueError(f"Expected a non-empty value for `agent_name` but received {agent_name!r}")
        return self._get(
            f"/agents/name/{agent_name}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Agent,
        )

    def rpc(
        self,
        agent_id: str,
        *,
        method: Literal["event/send", "task/create", "message/send", "task/cancel"],
        params: agent_rpc_params.Params,
        id: Union[int, str, None] | NotGiven = NOT_GIVEN,
        jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentRpcResponse:
        """
        Handle JSON-RPC requests for an agent by its unique ID.

        Args:
          params: The parameters for the agent RPC request

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return self._post(
            f"/agents/{agent_id}/rpc",
            body=maybe_transform(
                {
                    "method": method,
                    "params": params,
                    "id": id,
                    "jsonrpc": jsonrpc,
                },
                agent_rpc_params.AgentRpcParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentRpcResponse,
        )

    def rpc_by_name(
        self,
        agent_name: str,
        *,
        method: Literal["event/send", "task/create", "message/send", "task/cancel"],
        params: agent_rpc_by_name_params.Params,
        id: Union[int, str, None] | NotGiven = NOT_GIVEN,
        jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentRpcResponse:
        """
        Handle JSON-RPC requests for an agent by its unique name.

        Args:
          params: The parameters for the agent RPC request

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_name:
            raise ValueError(f"Expected a non-empty value for `agent_name` but received {agent_name!r}")
        return self._post(
            f"/agents/name/{agent_name}/rpc",
            body=maybe_transform(
                {
                    "method": method,
                    "params": params,
                    "id": id,
                    "jsonrpc": jsonrpc,
                },
                agent_rpc_by_name_params.AgentRpcByNameParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentRpcResponse,
        )
    
    def create_task(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsCreateTaskRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> CreateTaskResponse:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if agent_id is not None:
        raw_agent_rpc_response = self.rpc(
          agent_id=agent_id,
          method="task/create",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      elif agent_name is not None:
        raw_agent_rpc_response = self.rpc_by_name(
          agent_name=agent_name,
          method="task/create",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      else:
        raise ValueError("Either agent_id or agent_name must be provided")
      
      return CreateTaskResponse.model_validate(raw_agent_rpc_response, from_attributes=True)
    
    def cancel_task(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsCancelTaskRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> CancelTaskResponse:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if agent_id is not None:
        raw_agent_rpc_response = self.rpc(
          agent_id=agent_id,
          method="task/cancel",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      elif agent_name is not None:
        raw_agent_rpc_response = self.rpc_by_name(
          agent_name=agent_name,
          method="task/cancel",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      else:
        raise ValueError("Either agent_id or agent_name must be provided")
      
      return CancelTaskResponse.model_validate(raw_agent_rpc_response, from_attributes=True)

    def send_message(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsSendMessageRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> SendMessageResponse:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if "stream" in params and params["stream"] == True:
        raise ValueError("If stream is set to True, use send_message_stream() instead")
      else:
        if agent_id is not None:
          raw_agent_rpc_response = self.rpc(
            agent_id=agent_id,
            method="message/send",
            params=params,
            id=id,
            jsonrpc=jsonrpc,
            extra_headers=extra_headers,
            extra_query=extra_query,
            extra_body=extra_body,
            timeout=timeout,
          )
        elif agent_name is not None:
          raw_agent_rpc_response = self.rpc_by_name(
            agent_name=agent_name,
            method="message/send",
            params=params,
            id=id,
            jsonrpc=jsonrpc,
            extra_headers=extra_headers,
            extra_query=extra_query,
            extra_body=extra_body,
            timeout=timeout,
          )
        else:
          raise ValueError("Either agent_id or agent_name must be provided")
        
        return SendMessageResponse.model_validate(raw_agent_rpc_response, from_attributes=True)
    
    def send_message_stream(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsSendMessageRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Generator[SendMessageStreamResponse, None, None]:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")

      if "stream" in params and params["stream"] == False:
        raise ValueError("If stream is set to False, use send_message() instead")
      
      params["stream"] = True
      
      if agent_id is not None:
        raw_agent_rpc_response = self.with_streaming_response.rpc(
          agent_id=agent_id,
          method="message/send",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      elif agent_name is not None:
        raw_agent_rpc_response = self.with_streaming_response.rpc_by_name(
          agent_name=agent_name,
          method="message/send",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      else:
        raise ValueError("Either agent_id or agent_name must be provided")
      
      with raw_agent_rpc_response as response:
        for _line in response.iter_lines():
          if not _line:
            continue
          line = _line.strip()
          # Handle optional SSE-style prefix
          if line.startswith("data:"):
            line = line[len("data:"):].strip()
          if not line:
            continue
          try:
            chunk_rpc_response = SendMessageStreamResponse.model_validate(
              json.loads(line),
              from_attributes=True
            )
            yield chunk_rpc_response
          except json.JSONDecodeError:
            # Skip invalid JSON lines
            continue
    
    def send_event(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsSendEventRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> SendEventResponse:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if agent_id is not None:
        raw_agent_rpc_response = self.rpc(
          agent_id=agent_id,
          method="event/send",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      elif agent_name is not None:
        raw_agent_rpc_response = self.rpc_by_name(
          agent_name=agent_name,
          method="event/send",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      else:
        raise ValueError("Either agent_id or agent_name must be provided")
      
      return SendEventResponse.model_validate(raw_agent_rpc_response, from_attributes=True)


class AsyncAgentsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncAgentsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncAgentsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncAgentsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/agentex-python#with_streaming_response
        """
        return AsyncAgentsResourceWithStreamingResponse(self)

    async def retrieve(
        self,
        agent_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Agent:
        """
        Get an agent by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return await self._get(
            f"/agents/{agent_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Agent,
        )

    async def list(
        self,
        *,
        task_id: Optional[str] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentListResponse:
        """
        List all registered agents, optionally filtered by query parameters.

        Args:
          task_id: Task ID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/agents",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"task_id": task_id}, agent_list_params.AgentListParams),
            ),
            cast_to=AgentListResponse,
        )

    async def delete(
        self,
        agent_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> DeleteResponse:
        """
        Delete an agent by its unique ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return await self._delete(
            f"/agents/{agent_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    async def delete_by_name(
        self,
        agent_name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> DeleteResponse:
        """
        Delete an agent by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_name:
            raise ValueError(f"Expected a non-empty value for `agent_name` but received {agent_name!r}")
        return await self._delete(
            f"/agents/name/{agent_name}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DeleteResponse,
        )

    async def retrieve_by_name(
        self,
        agent_name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> Agent:
        """
        Get an agent by its unique name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_name:
            raise ValueError(f"Expected a non-empty value for `agent_name` but received {agent_name!r}")
        return await self._get(
            f"/agents/name/{agent_name}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Agent,
        )

    async def rpc(
        self,
        agent_id: str,
        *,
        method: Literal["event/send", "task/create", "message/send", "task/cancel"],
        params: agent_rpc_params.Params,
        id: Union[int, str, None] | NotGiven = NOT_GIVEN,
        jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentRpcResponse:
        """
        Handle JSON-RPC requests for an agent by its unique ID.

        Args:
          params: The parameters for the agent RPC request

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_id:
            raise ValueError(f"Expected a non-empty value for `agent_id` but received {agent_id!r}")
        return await self._post(
            f"/agents/{agent_id}/rpc",
            body=await async_maybe_transform(
                {
                    "method": method,
                    "params": params,
                    "id": id,
                    "jsonrpc": jsonrpc,
                },
                agent_rpc_params.AgentRpcParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentRpcResponse,
        )

    async def rpc_by_name(
        self,
        agent_name: str,
        *,
        method: Literal["event/send", "task/create", "message/send", "task/cancel"],
        params: agent_rpc_by_name_params.Params,
        id: Union[int, str, None] | NotGiven = NOT_GIVEN,
        jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AgentRpcResponse:
        """
        Handle JSON-RPC requests for an agent by its unique name.

        Args:
          params: The parameters for the agent RPC request

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not agent_name:
            raise ValueError(f"Expected a non-empty value for `agent_name` but received {agent_name!r}")
        return await self._post(
            f"/agents/name/{agent_name}/rpc",
            body=await async_maybe_transform(
                {
                    "method": method,
                    "params": params,
                    "id": id,
                    "jsonrpc": jsonrpc,
                },
                agent_rpc_by_name_params.AgentRpcByNameParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentRpcResponse,
        )
    
    async def create_task(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsCreateTaskRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> CreateTaskResponse:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if agent_id is not None:
        raw_agent_rpc_response = await self.rpc(
          agent_id=agent_id,
          method="task/create",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      elif agent_name is not None:
        raw_agent_rpc_response = await self.rpc_by_name(
          agent_name=agent_name,
          method="task/create",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      else:
        raise ValueError("Either agent_id or agent_name must be provided")
      
      return CreateTaskResponse.model_validate(raw_agent_rpc_response, from_attributes=True)
    
    async def cancel_task(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsCancelTaskRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> CancelTaskResponse:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if agent_id is not None:
        raw_agent_rpc_response = await self.rpc(
          agent_id=agent_id,
          method="task/cancel",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      elif agent_name is not None:
        raw_agent_rpc_response = await self.rpc_by_name(
          agent_name=agent_name,
          method="task/cancel",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      else:
        raise ValueError("Either agent_id or agent_name must be provided")
      
      return CancelTaskResponse.model_validate(raw_agent_rpc_response, from_attributes=True)

    async def send_message(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsSendMessageRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> SendMessageResponse:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if "stream" in params and params["stream"] == True:
        raise ValueError("If stream is set to True, use send_message_stream() instead")
      else:
        if agent_id is not None:
          raw_agent_rpc_response = await self.rpc(
            agent_id=agent_id,
            method="message/send",
            params=params,
            id=id,
            jsonrpc=jsonrpc,
            extra_headers=extra_headers,
            extra_query=extra_query,
            extra_body=extra_body,
            timeout=timeout,
          )
        elif agent_name is not None:
          raw_agent_rpc_response = await self.rpc_by_name(
            agent_name=agent_name,
            method="message/send",
            params=params,
            id=id,
            jsonrpc=jsonrpc,
            extra_headers=extra_headers,
            extra_query=extra_query,
            extra_body=extra_body,
            timeout=timeout,
          )
        else:
          raise ValueError("Either agent_id or agent_name must be provided")
        
        return SendMessageResponse.model_validate(raw_agent_rpc_response, from_attributes=True)
    
    async def send_message_stream(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsSendMessageRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> AsyncGenerator[SendMessageStreamResponse, None]:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if "stream" in params and params["stream"] == False:
        raise ValueError("If stream is set to False, use send_message() instead")
      
      params["stream"] = True
      
      if agent_id is not None:
        raw_agent_rpc_response = self.with_streaming_response.rpc(
          agent_id=agent_id,
          method="message/send",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      elif agent_name is not None:
        raw_agent_rpc_response = self.with_streaming_response.rpc_by_name(
          agent_name=agent_name,
          method="message/send",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      else:
        raise ValueError("Either agent_id or agent_name must be provided")
      
      async with raw_agent_rpc_response as response:
        async for _line in response.iter_lines():
          if not _line:
            continue
          line = _line.strip()
          # Handle optional SSE-style prefix
          if line.startswith("data:"):
            line = line[len("data:"):].strip()
          if not line:
            continue
          try:
            chunk_rpc_response = SendMessageStreamResponse.model_validate(
              json.loads(line),
              from_attributes=True
            )
            yield chunk_rpc_response
          except json.JSONDecodeError:
            # Skip invalid JSON lines
            continue
    
    async def send_event(
      self,
      agent_id: str | None = None,
      agent_name: str | None = None,
      *,
      params: agent_rpc_params.ParamsSendEventRequest,
      id: Union[int, str, None] | NotGiven = NOT_GIVEN,
      jsonrpc: Literal["2.0"] | NotGiven = NOT_GIVEN,
      # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
      # The extra values given here take precedence over values defined on the client or passed to this method.
      extra_headers: Headers | None = None,
      extra_query: Query | None = None,
      extra_body: Body | None = None,
      timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> SendEventResponse:
      if agent_id is not None and agent_name is not None:
        raise ValueError("Either agent_id or agent_name must be provided, but not both")
      
      if agent_id is not None:
        raw_agent_rpc_response = await self.rpc(
          agent_id=agent_id,
          method="event/send",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      elif agent_name is not None:
        raw_agent_rpc_response = await self.rpc_by_name(
          agent_name=agent_name,
          method="event/send",
          params=params,
          id=id,
          jsonrpc=jsonrpc,
          extra_headers=extra_headers,
          extra_query=extra_query,
          extra_body=extra_body,
          timeout=timeout,
        )
      else:
        raise ValueError("Either agent_id or agent_name must be provided")
      
      return SendEventResponse.model_validate(raw_agent_rpc_response, from_attributes=True)

class AgentsResourceWithRawResponse:
    def __init__(self, agents: AgentsResource) -> None:
        self._agents = agents

        self.retrieve = to_raw_response_wrapper(
            agents.retrieve,
        )
        self.list = to_raw_response_wrapper(
            agents.list,
        )
        self.delete = to_raw_response_wrapper(
            agents.delete,
        )
        self.delete_by_name = to_raw_response_wrapper(
            agents.delete_by_name,
        )
        self.retrieve_by_name = to_raw_response_wrapper(
            agents.retrieve_by_name,
        )
        self.rpc = to_raw_response_wrapper(
            agents.rpc,
        )
        self.rpc_by_name = to_raw_response_wrapper(
            agents.rpc_by_name,
        )


class AsyncAgentsResourceWithRawResponse:
    def __init__(self, agents: AsyncAgentsResource) -> None:
        self._agents = agents

        self.retrieve = async_to_raw_response_wrapper(
            agents.retrieve,
        )
        self.list = async_to_raw_response_wrapper(
            agents.list,
        )
        self.delete = async_to_raw_response_wrapper(
            agents.delete,
        )
        self.delete_by_name = async_to_raw_response_wrapper(
            agents.delete_by_name,
        )
        self.retrieve_by_name = async_to_raw_response_wrapper(
            agents.retrieve_by_name,
        )
        self.rpc = async_to_raw_response_wrapper(
            agents.rpc,
        )
        self.rpc_by_name = async_to_raw_response_wrapper(
            agents.rpc_by_name,
        )


class AgentsResourceWithStreamingResponse:
    def __init__(self, agents: AgentsResource) -> None:
        self._agents = agents

        self.retrieve = to_streamed_response_wrapper(
            agents.retrieve,
        )
        self.list = to_streamed_response_wrapper(
            agents.list,
        )
        self.delete = to_streamed_response_wrapper(
            agents.delete,
        )
        self.delete_by_name = to_streamed_response_wrapper(
            agents.delete_by_name,
        )
        self.retrieve_by_name = to_streamed_response_wrapper(
            agents.retrieve_by_name,
        )
        self.rpc = to_streamed_response_wrapper(
            agents.rpc,
        )
        self.rpc_by_name = to_streamed_response_wrapper(
            agents.rpc_by_name,
        )


class AsyncAgentsResourceWithStreamingResponse:
    def __init__(self, agents: AsyncAgentsResource) -> None:
        self._agents = agents

        self.retrieve = async_to_streamed_response_wrapper(
            agents.retrieve,
        )
        self.list = async_to_streamed_response_wrapper(
            agents.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            agents.delete,
        )
        self.delete_by_name = async_to_streamed_response_wrapper(
            agents.delete_by_name,
        )
        self.retrieve_by_name = async_to_streamed_response_wrapper(
            agents.retrieve_by_name,
        )
        self.rpc = async_to_streamed_response_wrapper(
            agents.rpc,
        )
        self.rpc_by_name = async_to_streamed_response_wrapper(
            agents.rpc_by_name,
        )
