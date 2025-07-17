# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, Union, Mapping
from typing_extensions import Self, override

import httpx

from . import _exceptions
from ._qs import Querystring
from ._types import (
    NOT_GIVEN,
    Body,
    Omit,
    Query,
    Headers,
    Timeout,
    NotGiven,
    Transport,
    ProxiesTypes,
    RequestOptions,
)
from ._utils import is_given, get_async_library
from ._version import __version__
from ._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .resources import echo, spans, events, states, tracker
from ._streaming import Stream as Stream, AsyncStream as AsyncStream
from ._exceptions import APIStatusError
from ._base_client import (
    DEFAULT_MAX_RETRIES,
    SyncAPIClient,
    AsyncAPIClient,
    make_request_options,
)
from .resources.tasks import tasks
from .resources.agents import agents
from .resources.messages import messages

__all__ = ["Timeout", "Transport", "ProxiesTypes", "RequestOptions", "Agentex", "AsyncAgentex", "Client", "AsyncClient"]


class Agentex(SyncAPIClient):
    echo: echo.EchoResource
    agents: agents.AgentsResource
    tasks: tasks.TasksResource
    messages: messages.MessagesResource
    spans: spans.SpansResource
    states: states.StatesResource
    events: events.EventsResource
    tracker: tracker.TrackerResource
    with_raw_response: AgentexWithRawResponse
    with_streaming_response: AgentexWithStreamedResponse

    # client options
    api_key: str | None

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: Union[float, Timeout, None, NotGiven] = NOT_GIVEN,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        # Configure a custom httpx client.
        # We provide a `DefaultHttpxClient` class that you can pass to retain the default values we use for `limits`, `timeout` & `follow_redirects`.
        # See the [httpx documentation](https://www.python-httpx.org/api/#client) for more details.
        http_client: httpx.Client | None = None,
        # Enable or disable schema validation for data returned by the API.
        # When enabled an error APIResponseValidationError is raised
        # if the API responds with invalid data for the expected schema.
        #
        # This parameter may be removed or changed in the future.
        # If you rely on this feature, please open a GitHub issue
        # outlining your use-case to help us decide if it should be
        # part of our public interface in the future.
        _strict_response_validation: bool = False,
    ) -> None:
        """Construct a new synchronous Agentex client instance.

        This automatically infers the `api_key` argument from the `AGENTEX_SDK_API_KEY` environment variable if it is not provided.
        """
        if api_key is None:
            api_key = os.environ.get("AGENTEX_SDK_API_KEY")
        self.api_key = api_key

        if base_url is None:
            base_url = os.environ.get("AGENTEX_BASE_URL")
        if base_url is None:
            base_url = f"https://api.example.com"

        super().__init__(
            version=__version__,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
            http_client=http_client,
            custom_headers=default_headers,
            custom_query=default_query,
            _strict_response_validation=_strict_response_validation,
        )

        self.echo = echo.EchoResource(self)
        self.agents = agents.AgentsResource(self)
        self.tasks = tasks.TasksResource(self)
        self.messages = messages.MessagesResource(self)
        self.spans = spans.SpansResource(self)
        self.states = states.StatesResource(self)
        self.events = events.EventsResource(self)
        self.tracker = tracker.TrackerResource(self)
        self.with_raw_response = AgentexWithRawResponse(self)
        self.with_streaming_response = AgentexWithStreamedResponse(self)

    @property
    @override
    def qs(self) -> Querystring:
        return Querystring(array_format="comma")

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        api_key = self.api_key
        if api_key is None:
            return {}
        return {"Authorization": f"Bearer {api_key}"}

    @property
    @override
    def default_headers(self) -> dict[str, str | Omit]:
        return {
            **super().default_headers,
            "X-Stainless-Async": "false",
            **self._custom_headers,
        }

    @override
    def _validate_headers(self, headers: Headers, custom_headers: Headers) -> None:
        if self.api_key and headers.get("Authorization"):
            return
        if isinstance(custom_headers.get("Authorization"), Omit):
            return

        raise TypeError(
            '"Could not resolve authentication method. Expected the api_key to be set. Or for the `Authorization` headers to be explicitly omitted"'
        )

    def copy(
        self,
        *,
        api_key: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = NOT_GIVEN,
        http_client: httpx.Client | None = None,
        max_retries: int | NotGiven = NOT_GIVEN,
        default_headers: Mapping[str, str] | None = None,
        set_default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        set_default_query: Mapping[str, object] | None = None,
        _extra_kwargs: Mapping[str, Any] = {},
    ) -> Self:
        """
        Create a new client instance re-using the same options given to the current client with optional overriding.
        """
        if default_headers is not None and set_default_headers is not None:
            raise ValueError("The `default_headers` and `set_default_headers` arguments are mutually exclusive")

        if default_query is not None and set_default_query is not None:
            raise ValueError("The `default_query` and `set_default_query` arguments are mutually exclusive")

        headers = self._custom_headers
        if default_headers is not None:
            headers = {**headers, **default_headers}
        elif set_default_headers is not None:
            headers = set_default_headers

        params = self._custom_query
        if default_query is not None:
            params = {**params, **default_query}
        elif set_default_query is not None:
            params = set_default_query

        http_client = http_client or self._client
        return self.__class__(
            api_key=api_key or self.api_key,
            base_url=base_url or self.base_url,
            timeout=self.timeout if isinstance(timeout, NotGiven) else timeout,
            http_client=http_client,
            max_retries=max_retries if is_given(max_retries) else self.max_retries,
            default_headers=headers,
            default_query=params,
            **_extra_kwargs,
        )

    # Alias for `copy` for nicer inline usage, e.g.
    # client.with_options(timeout=10).foo.create(...)
    with_options = copy

    def get_root(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> object:
        """Root"""
        return self.get(
            "/",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    @override
    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ) -> APIStatusError:
        if response.status_code == 400:
            return _exceptions.BadRequestError(err_msg, response=response, body=body)

        if response.status_code == 401:
            return _exceptions.AuthenticationError(err_msg, response=response, body=body)

        if response.status_code == 403:
            return _exceptions.PermissionDeniedError(err_msg, response=response, body=body)

        if response.status_code == 404:
            return _exceptions.NotFoundError(err_msg, response=response, body=body)

        if response.status_code == 409:
            return _exceptions.ConflictError(err_msg, response=response, body=body)

        if response.status_code == 422:
            return _exceptions.UnprocessableEntityError(err_msg, response=response, body=body)

        if response.status_code == 429:
            return _exceptions.RateLimitError(err_msg, response=response, body=body)

        if response.status_code >= 500:
            return _exceptions.InternalServerError(err_msg, response=response, body=body)
        return APIStatusError(err_msg, response=response, body=body)


class AsyncAgentex(AsyncAPIClient):
    echo: echo.AsyncEchoResource
    agents: agents.AsyncAgentsResource
    tasks: tasks.AsyncTasksResource
    messages: messages.AsyncMessagesResource
    spans: spans.AsyncSpansResource
    states: states.AsyncStatesResource
    events: events.AsyncEventsResource
    tracker: tracker.AsyncTrackerResource
    with_raw_response: AsyncAgentexWithRawResponse
    with_streaming_response: AsyncAgentexWithStreamedResponse

    # client options
    api_key: str | None

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: Union[float, Timeout, None, NotGiven] = NOT_GIVEN,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        # Configure a custom httpx client.
        # We provide a `DefaultAsyncHttpxClient` class that you can pass to retain the default values we use for `limits`, `timeout` & `follow_redirects`.
        # See the [httpx documentation](https://www.python-httpx.org/api/#asyncclient) for more details.
        http_client: httpx.AsyncClient | None = None,
        # Enable or disable schema validation for data returned by the API.
        # When enabled an error APIResponseValidationError is raised
        # if the API responds with invalid data for the expected schema.
        #
        # This parameter may be removed or changed in the future.
        # If you rely on this feature, please open a GitHub issue
        # outlining your use-case to help us decide if it should be
        # part of our public interface in the future.
        _strict_response_validation: bool = False,
    ) -> None:
        """Construct a new async AsyncAgentex client instance.

        This automatically infers the `api_key` argument from the `AGENTEX_SDK_API_KEY` environment variable if it is not provided.
        """
        if api_key is None:
            api_key = os.environ.get("AGENTEX_SDK_API_KEY")
        self.api_key = api_key

        if base_url is None:
            base_url = os.environ.get("AGENTEX_BASE_URL")
        if base_url is None:
            base_url = f"https://api.example.com"

        super().__init__(
            version=__version__,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
            http_client=http_client,
            custom_headers=default_headers,
            custom_query=default_query,
            _strict_response_validation=_strict_response_validation,
        )

        self.echo = echo.AsyncEchoResource(self)
        self.agents = agents.AsyncAgentsResource(self)
        self.tasks = tasks.AsyncTasksResource(self)
        self.messages = messages.AsyncMessagesResource(self)
        self.spans = spans.AsyncSpansResource(self)
        self.states = states.AsyncStatesResource(self)
        self.events = events.AsyncEventsResource(self)
        self.tracker = tracker.AsyncTrackerResource(self)
        self.with_raw_response = AsyncAgentexWithRawResponse(self)
        self.with_streaming_response = AsyncAgentexWithStreamedResponse(self)

    @property
    @override
    def qs(self) -> Querystring:
        return Querystring(array_format="comma")

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        api_key = self.api_key
        if api_key is None:
            return {}
        return {"Authorization": f"Bearer {api_key}"}

    @property
    @override
    def default_headers(self) -> dict[str, str | Omit]:
        return {
            **super().default_headers,
            "X-Stainless-Async": f"async:{get_async_library()}",
            **self._custom_headers,
        }

    @override
    def _validate_headers(self, headers: Headers, custom_headers: Headers) -> None:
        if self.api_key and headers.get("Authorization"):
            return
        if isinstance(custom_headers.get("Authorization"), Omit):
            return

        raise TypeError(
            '"Could not resolve authentication method. Expected the api_key to be set. Or for the `Authorization` headers to be explicitly omitted"'
        )

    def copy(
        self,
        *,
        api_key: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = NOT_GIVEN,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int | NotGiven = NOT_GIVEN,
        default_headers: Mapping[str, str] | None = None,
        set_default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        set_default_query: Mapping[str, object] | None = None,
        _extra_kwargs: Mapping[str, Any] = {},
    ) -> Self:
        """
        Create a new client instance re-using the same options given to the current client with optional overriding.
        """
        if default_headers is not None and set_default_headers is not None:
            raise ValueError("The `default_headers` and `set_default_headers` arguments are mutually exclusive")

        if default_query is not None and set_default_query is not None:
            raise ValueError("The `default_query` and `set_default_query` arguments are mutually exclusive")

        headers = self._custom_headers
        if default_headers is not None:
            headers = {**headers, **default_headers}
        elif set_default_headers is not None:
            headers = set_default_headers

        params = self._custom_query
        if default_query is not None:
            params = {**params, **default_query}
        elif set_default_query is not None:
            params = set_default_query

        http_client = http_client or self._client
        return self.__class__(
            api_key=api_key or self.api_key,
            base_url=base_url or self.base_url,
            timeout=self.timeout if isinstance(timeout, NotGiven) else timeout,
            http_client=http_client,
            max_retries=max_retries if is_given(max_retries) else self.max_retries,
            default_headers=headers,
            default_query=params,
            **_extra_kwargs,
        )

    # Alias for `copy` for nicer inline usage, e.g.
    # client.with_options(timeout=10).foo.create(...)
    with_options = copy

    async def get_root(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> object:
        """Root"""
        return await self.get(
            "/",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    @override
    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ) -> APIStatusError:
        if response.status_code == 400:
            return _exceptions.BadRequestError(err_msg, response=response, body=body)

        if response.status_code == 401:
            return _exceptions.AuthenticationError(err_msg, response=response, body=body)

        if response.status_code == 403:
            return _exceptions.PermissionDeniedError(err_msg, response=response, body=body)

        if response.status_code == 404:
            return _exceptions.NotFoundError(err_msg, response=response, body=body)

        if response.status_code == 409:
            return _exceptions.ConflictError(err_msg, response=response, body=body)

        if response.status_code == 422:
            return _exceptions.UnprocessableEntityError(err_msg, response=response, body=body)

        if response.status_code == 429:
            return _exceptions.RateLimitError(err_msg, response=response, body=body)

        if response.status_code >= 500:
            return _exceptions.InternalServerError(err_msg, response=response, body=body)
        return APIStatusError(err_msg, response=response, body=body)


class AgentexWithRawResponse:
    def __init__(self, client: Agentex) -> None:
        self.echo = echo.EchoResourceWithRawResponse(client.echo)
        self.agents = agents.AgentsResourceWithRawResponse(client.agents)
        self.tasks = tasks.TasksResourceWithRawResponse(client.tasks)
        self.messages = messages.MessagesResourceWithRawResponse(client.messages)
        self.spans = spans.SpansResourceWithRawResponse(client.spans)
        self.states = states.StatesResourceWithRawResponse(client.states)
        self.events = events.EventsResourceWithRawResponse(client.events)
        self.tracker = tracker.TrackerResourceWithRawResponse(client.tracker)

        self.get_root = to_raw_response_wrapper(
            client.get_root,
        )


class AsyncAgentexWithRawResponse:
    def __init__(self, client: AsyncAgentex) -> None:
        self.echo = echo.AsyncEchoResourceWithRawResponse(client.echo)
        self.agents = agents.AsyncAgentsResourceWithRawResponse(client.agents)
        self.tasks = tasks.AsyncTasksResourceWithRawResponse(client.tasks)
        self.messages = messages.AsyncMessagesResourceWithRawResponse(client.messages)
        self.spans = spans.AsyncSpansResourceWithRawResponse(client.spans)
        self.states = states.AsyncStatesResourceWithRawResponse(client.states)
        self.events = events.AsyncEventsResourceWithRawResponse(client.events)
        self.tracker = tracker.AsyncTrackerResourceWithRawResponse(client.tracker)

        self.get_root = async_to_raw_response_wrapper(
            client.get_root,
        )


class AgentexWithStreamedResponse:
    def __init__(self, client: Agentex) -> None:
        self.echo = echo.EchoResourceWithStreamingResponse(client.echo)
        self.agents = agents.AgentsResourceWithStreamingResponse(client.agents)
        self.tasks = tasks.TasksResourceWithStreamingResponse(client.tasks)
        self.messages = messages.MessagesResourceWithStreamingResponse(client.messages)
        self.spans = spans.SpansResourceWithStreamingResponse(client.spans)
        self.states = states.StatesResourceWithStreamingResponse(client.states)
        self.events = events.EventsResourceWithStreamingResponse(client.events)
        self.tracker = tracker.TrackerResourceWithStreamingResponse(client.tracker)

        self.get_root = to_streamed_response_wrapper(
            client.get_root,
        )


class AsyncAgentexWithStreamedResponse:
    def __init__(self, client: AsyncAgentex) -> None:
        self.echo = echo.AsyncEchoResourceWithStreamingResponse(client.echo)
        self.agents = agents.AsyncAgentsResourceWithStreamingResponse(client.agents)
        self.tasks = tasks.AsyncTasksResourceWithStreamingResponse(client.tasks)
        self.messages = messages.AsyncMessagesResourceWithStreamingResponse(client.messages)
        self.spans = spans.AsyncSpansResourceWithStreamingResponse(client.spans)
        self.states = states.AsyncStatesResourceWithStreamingResponse(client.states)
        self.events = events.AsyncEventsResourceWithStreamingResponse(client.events)
        self.tracker = tracker.AsyncTrackerResourceWithStreamingResponse(client.tracker)

        self.get_root = async_to_streamed_response_wrapper(
            client.get_root,
        )


Client = Agentex

AsyncClient = AsyncAgentex
