# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..types import echo_send_params
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

__all__ = ["EchoResource", "AsyncEchoResource"]


class EchoResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> EchoResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/agentex-sdk-python#accessing-raw-response-data-eg-headers
        """
        return EchoResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> EchoResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/agentex-sdk-python#with_streaming_response
        """
        return EchoResourceWithStreamingResponse(self)

    def send(
        self,
        *,
        message: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> object:
        """
        Echo

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/echo",
            body=maybe_transform({"message": message}, echo_send_params.EchoSendParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncEchoResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncEchoResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/agentex-sdk-python#accessing-raw-response-data-eg-headers
        """
        return AsyncEchoResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncEchoResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/agentex-sdk-python#with_streaming_response
        """
        return AsyncEchoResourceWithStreamingResponse(self)

    async def send(
        self,
        *,
        message: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> object:
        """
        Echo

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/echo",
            body=await async_maybe_transform({"message": message}, echo_send_params.EchoSendParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class EchoResourceWithRawResponse:
    def __init__(self, echo: EchoResource) -> None:
        self._echo = echo

        self.send = to_raw_response_wrapper(
            echo.send,
        )


class AsyncEchoResourceWithRawResponse:
    def __init__(self, echo: AsyncEchoResource) -> None:
        self._echo = echo

        self.send = async_to_raw_response_wrapper(
            echo.send,
        )


class EchoResourceWithStreamingResponse:
    def __init__(self, echo: EchoResource) -> None:
        self._echo = echo

        self.send = to_streamed_response_wrapper(
            echo.send,
        )


class AsyncEchoResourceWithStreamingResponse:
    def __init__(self, echo: AsyncEchoResource) -> None:
        self._echo = echo

        self.send = async_to_streamed_response_wrapper(
            echo.send,
        )
