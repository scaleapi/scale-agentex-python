# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, Mapping, cast
from typing_extensions import Self, Literal, override

import httpx

from . import _exceptions
from ._qs import Querystring
from ._types import (
    Omit,
    Timeout,
    NotGiven,
    Transport,
    ProxiesTypes,
    RequestOptions,
    not_given,
)
from ._utils import is_given, get_async_library
from ._compat import cached_property
from ._version import __version__
from ._streaming import Stream as Stream, AsyncStream as AsyncStream
from ._exceptions import APIStatusError
from ._base_client import (
    DEFAULT_MAX_RETRIES,
    SyncAPIClient,
    AsyncAPIClient,
)

if TYPE_CHECKING:
    from .resources import spans, tasks, agents, events, states, tracker, messages, deployment_history
    from .resources.spans import SpansResource, AsyncSpansResource
    from .resources.tasks import TasksResource, AsyncTasksResource
    from .resources.agents import AgentsResource, AsyncAgentsResource
    from .resources.events import EventsResource, AsyncEventsResource
    from .resources.states import StatesResource, AsyncStatesResource
    from .resources.tracker import TrackerResource, AsyncTrackerResource
    from .resources.messages.messages import MessagesResource, AsyncMessagesResource
    from .resources.deployment_history import DeploymentHistoryResource, AsyncDeploymentHistoryResource

__all__ = [
    "ENVIRONMENTS",
    "Timeout",
    "Transport",
    "ProxiesTypes",
    "RequestOptions",
    "Agentex",
    "AsyncAgentex",
    "Client",
    "AsyncClient",
]

ENVIRONMENTS: Dict[str, str] = {
    "production": "http://localhost:5003",
    "development": "http://localhost:5003",
}


class Agentex(SyncAPIClient):
    # client options
    api_key: str | None

    _environment: Literal["production", "development"] | NotGiven

    def __init__(
        self,
        *,
        api_key: str | None = None,
        environment: Literal["production", "development"] | NotGiven = not_given,
        base_url: str | httpx.URL | None | NotGiven = not_given,
        timeout: float | Timeout | None | NotGiven = not_given,
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

        self._environment = environment

        base_url_env = os.environ.get("AGENTEX_BASE_URL")
        if is_given(base_url) and base_url is not None:
            # cast required because mypy doesn't understand the type narrowing
            base_url = cast("str | httpx.URL", base_url)  # pyright: ignore[reportUnnecessaryCast]
        elif is_given(environment):
            if base_url_env and base_url is not None:
                raise ValueError(
                    "Ambiguous URL; The `AGENTEX_BASE_URL` env var and the `environment` argument are given. If you want to use the environment, you must pass base_url=None",
                )

            try:
                base_url = ENVIRONMENTS[environment]
            except KeyError as exc:
                raise ValueError(f"Unknown environment: {environment}") from exc
        elif base_url_env is not None:
            base_url = base_url_env
        else:
            self._environment = environment = "production"

            try:
                base_url = ENVIRONMENTS[environment]
            except KeyError as exc:
                raise ValueError(f"Unknown environment: {environment}") from exc

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

    @cached_property
    def agents(self) -> AgentsResource:
        from .resources.agents import AgentsResource

        return AgentsResource(self)

    @cached_property
    def tasks(self) -> TasksResource:
        from .resources.tasks import TasksResource

        return TasksResource(self)

    @cached_property
    def messages(self) -> MessagesResource:
        from .resources.messages import MessagesResource

        return MessagesResource(self)

    @cached_property
    def spans(self) -> SpansResource:
        from .resources.spans import SpansResource

        return SpansResource(self)

    @cached_property
    def states(self) -> StatesResource:
        from .resources.states import StatesResource

        return StatesResource(self)

    @cached_property
    def events(self) -> EventsResource:
        from .resources.events import EventsResource

        return EventsResource(self)

    @cached_property
    def tracker(self) -> TrackerResource:
        from .resources.tracker import TrackerResource

        return TrackerResource(self)

    @cached_property
    def deployment_history(self) -> DeploymentHistoryResource:
        from .resources.deployment_history import DeploymentHistoryResource

        return DeploymentHistoryResource(self)

    @cached_property
    def with_raw_response(self) -> AgentexWithRawResponse:
        return AgentexWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AgentexWithStreamedResponse:
        return AgentexWithStreamedResponse(self)

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

    def copy(
        self,
        *,
        api_key: str | None = None,
        environment: Literal["production", "development"] | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        http_client: httpx.Client | None = None,
        max_retries: int | NotGiven = not_given,
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
            environment=environment or self._environment,
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
    # client options
    api_key: str | None

    _environment: Literal["production", "development"] | NotGiven

    def __init__(
        self,
        *,
        api_key: str | None = None,
        environment: Literal["production", "development"] | NotGiven = not_given,
        base_url: str | httpx.URL | None | NotGiven = not_given,
        timeout: float | Timeout | None | NotGiven = not_given,
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

        self._environment = environment

        base_url_env = os.environ.get("AGENTEX_BASE_URL")
        if is_given(base_url) and base_url is not None:
            # cast required because mypy doesn't understand the type narrowing
            base_url = cast("str | httpx.URL", base_url)  # pyright: ignore[reportUnnecessaryCast]
        elif is_given(environment):
            if base_url_env and base_url is not None:
                raise ValueError(
                    "Ambiguous URL; The `AGENTEX_BASE_URL` env var and the `environment` argument are given. If you want to use the environment, you must pass base_url=None",
                )

            try:
                base_url = ENVIRONMENTS[environment]
            except KeyError as exc:
                raise ValueError(f"Unknown environment: {environment}") from exc
        elif base_url_env is not None:
            base_url = base_url_env
        else:
            self._environment = environment = "production"

            try:
                base_url = ENVIRONMENTS[environment]
            except KeyError as exc:
                raise ValueError(f"Unknown environment: {environment}") from exc

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

    @cached_property
    def agents(self) -> AsyncAgentsResource:
        from .resources.agents import AsyncAgentsResource

        return AsyncAgentsResource(self)

    @cached_property
    def tasks(self) -> AsyncTasksResource:
        from .resources.tasks import AsyncTasksResource

        return AsyncTasksResource(self)

    @cached_property
    def messages(self) -> AsyncMessagesResource:
        from .resources.messages import AsyncMessagesResource

        return AsyncMessagesResource(self)

    @cached_property
    def spans(self) -> AsyncSpansResource:
        from .resources.spans import AsyncSpansResource

        return AsyncSpansResource(self)

    @cached_property
    def states(self) -> AsyncStatesResource:
        from .resources.states import AsyncStatesResource

        return AsyncStatesResource(self)

    @cached_property
    def events(self) -> AsyncEventsResource:
        from .resources.events import AsyncEventsResource

        return AsyncEventsResource(self)

    @cached_property
    def tracker(self) -> AsyncTrackerResource:
        from .resources.tracker import AsyncTrackerResource

        return AsyncTrackerResource(self)

    @cached_property
    def deployment_history(self) -> AsyncDeploymentHistoryResource:
        from .resources.deployment_history import AsyncDeploymentHistoryResource

        return AsyncDeploymentHistoryResource(self)

    @cached_property
    def with_raw_response(self) -> AsyncAgentexWithRawResponse:
        return AsyncAgentexWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncAgentexWithStreamedResponse:
        return AsyncAgentexWithStreamedResponse(self)

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

    def copy(
        self,
        *,
        api_key: str | None = None,
        environment: Literal["production", "development"] | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int | NotGiven = not_given,
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
            environment=environment or self._environment,
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
    _client: Agentex

    def __init__(self, client: Agentex) -> None:
        self._client = client

    @cached_property
    def agents(self) -> agents.AgentsResourceWithRawResponse:
        from .resources.agents import AgentsResourceWithRawResponse

        return AgentsResourceWithRawResponse(self._client.agents)

    @cached_property
    def tasks(self) -> tasks.TasksResourceWithRawResponse:
        from .resources.tasks import TasksResourceWithRawResponse

        return TasksResourceWithRawResponse(self._client.tasks)

    @cached_property
    def messages(self) -> messages.MessagesResourceWithRawResponse:
        from .resources.messages import MessagesResourceWithRawResponse

        return MessagesResourceWithRawResponse(self._client.messages)

    @cached_property
    def spans(self) -> spans.SpansResourceWithRawResponse:
        from .resources.spans import SpansResourceWithRawResponse

        return SpansResourceWithRawResponse(self._client.spans)

    @cached_property
    def states(self) -> states.StatesResourceWithRawResponse:
        from .resources.states import StatesResourceWithRawResponse

        return StatesResourceWithRawResponse(self._client.states)

    @cached_property
    def events(self) -> events.EventsResourceWithRawResponse:
        from .resources.events import EventsResourceWithRawResponse

        return EventsResourceWithRawResponse(self._client.events)

    @cached_property
    def tracker(self) -> tracker.TrackerResourceWithRawResponse:
        from .resources.tracker import TrackerResourceWithRawResponse

        return TrackerResourceWithRawResponse(self._client.tracker)

    @cached_property
    def deployment_history(self) -> deployment_history.DeploymentHistoryResourceWithRawResponse:
        from .resources.deployment_history import DeploymentHistoryResourceWithRawResponse

        return DeploymentHistoryResourceWithRawResponse(self._client.deployment_history)


class AsyncAgentexWithRawResponse:
    _client: AsyncAgentex

    def __init__(self, client: AsyncAgentex) -> None:
        self._client = client

    @cached_property
    def agents(self) -> agents.AsyncAgentsResourceWithRawResponse:
        from .resources.agents import AsyncAgentsResourceWithRawResponse

        return AsyncAgentsResourceWithRawResponse(self._client.agents)

    @cached_property
    def tasks(self) -> tasks.AsyncTasksResourceWithRawResponse:
        from .resources.tasks import AsyncTasksResourceWithRawResponse

        return AsyncTasksResourceWithRawResponse(self._client.tasks)

    @cached_property
    def messages(self) -> messages.AsyncMessagesResourceWithRawResponse:
        from .resources.messages import AsyncMessagesResourceWithRawResponse

        return AsyncMessagesResourceWithRawResponse(self._client.messages)

    @cached_property
    def spans(self) -> spans.AsyncSpansResourceWithRawResponse:
        from .resources.spans import AsyncSpansResourceWithRawResponse

        return AsyncSpansResourceWithRawResponse(self._client.spans)

    @cached_property
    def states(self) -> states.AsyncStatesResourceWithRawResponse:
        from .resources.states import AsyncStatesResourceWithRawResponse

        return AsyncStatesResourceWithRawResponse(self._client.states)

    @cached_property
    def events(self) -> events.AsyncEventsResourceWithRawResponse:
        from .resources.events import AsyncEventsResourceWithRawResponse

        return AsyncEventsResourceWithRawResponse(self._client.events)

    @cached_property
    def tracker(self) -> tracker.AsyncTrackerResourceWithRawResponse:
        from .resources.tracker import AsyncTrackerResourceWithRawResponse

        return AsyncTrackerResourceWithRawResponse(self._client.tracker)

    @cached_property
    def deployment_history(self) -> deployment_history.AsyncDeploymentHistoryResourceWithRawResponse:
        from .resources.deployment_history import AsyncDeploymentHistoryResourceWithRawResponse

        return AsyncDeploymentHistoryResourceWithRawResponse(self._client.deployment_history)


class AgentexWithStreamedResponse:
    _client: Agentex

    def __init__(self, client: Agentex) -> None:
        self._client = client

    @cached_property
    def agents(self) -> agents.AgentsResourceWithStreamingResponse:
        from .resources.agents import AgentsResourceWithStreamingResponse

        return AgentsResourceWithStreamingResponse(self._client.agents)

    @cached_property
    def tasks(self) -> tasks.TasksResourceWithStreamingResponse:
        from .resources.tasks import TasksResourceWithStreamingResponse

        return TasksResourceWithStreamingResponse(self._client.tasks)

    @cached_property
    def messages(self) -> messages.MessagesResourceWithStreamingResponse:
        from .resources.messages import MessagesResourceWithStreamingResponse

        return MessagesResourceWithStreamingResponse(self._client.messages)

    @cached_property
    def spans(self) -> spans.SpansResourceWithStreamingResponse:
        from .resources.spans import SpansResourceWithStreamingResponse

        return SpansResourceWithStreamingResponse(self._client.spans)

    @cached_property
    def states(self) -> states.StatesResourceWithStreamingResponse:
        from .resources.states import StatesResourceWithStreamingResponse

        return StatesResourceWithStreamingResponse(self._client.states)

    @cached_property
    def events(self) -> events.EventsResourceWithStreamingResponse:
        from .resources.events import EventsResourceWithStreamingResponse

        return EventsResourceWithStreamingResponse(self._client.events)

    @cached_property
    def tracker(self) -> tracker.TrackerResourceWithStreamingResponse:
        from .resources.tracker import TrackerResourceWithStreamingResponse

        return TrackerResourceWithStreamingResponse(self._client.tracker)

    @cached_property
    def deployment_history(self) -> deployment_history.DeploymentHistoryResourceWithStreamingResponse:
        from .resources.deployment_history import DeploymentHistoryResourceWithStreamingResponse

        return DeploymentHistoryResourceWithStreamingResponse(self._client.deployment_history)


class AsyncAgentexWithStreamedResponse:
    _client: AsyncAgentex

    def __init__(self, client: AsyncAgentex) -> None:
        self._client = client

    @cached_property
    def agents(self) -> agents.AsyncAgentsResourceWithStreamingResponse:
        from .resources.agents import AsyncAgentsResourceWithStreamingResponse

        return AsyncAgentsResourceWithStreamingResponse(self._client.agents)

    @cached_property
    def tasks(self) -> tasks.AsyncTasksResourceWithStreamingResponse:
        from .resources.tasks import AsyncTasksResourceWithStreamingResponse

        return AsyncTasksResourceWithStreamingResponse(self._client.tasks)

    @cached_property
    def messages(self) -> messages.AsyncMessagesResourceWithStreamingResponse:
        from .resources.messages import AsyncMessagesResourceWithStreamingResponse

        return AsyncMessagesResourceWithStreamingResponse(self._client.messages)

    @cached_property
    def spans(self) -> spans.AsyncSpansResourceWithStreamingResponse:
        from .resources.spans import AsyncSpansResourceWithStreamingResponse

        return AsyncSpansResourceWithStreamingResponse(self._client.spans)

    @cached_property
    def states(self) -> states.AsyncStatesResourceWithStreamingResponse:
        from .resources.states import AsyncStatesResourceWithStreamingResponse

        return AsyncStatesResourceWithStreamingResponse(self._client.states)

    @cached_property
    def events(self) -> events.AsyncEventsResourceWithStreamingResponse:
        from .resources.events import AsyncEventsResourceWithStreamingResponse

        return AsyncEventsResourceWithStreamingResponse(self._client.events)

    @cached_property
    def tracker(self) -> tracker.AsyncTrackerResourceWithStreamingResponse:
        from .resources.tracker import AsyncTrackerResourceWithStreamingResponse

        return AsyncTrackerResourceWithStreamingResponse(self._client.tracker)

    @cached_property
    def deployment_history(self) -> deployment_history.AsyncDeploymentHistoryResourceWithStreamingResponse:
        from .resources.deployment_history import AsyncDeploymentHistoryResourceWithStreamingResponse

        return AsyncDeploymentHistoryResourceWithStreamingResponse(self._client.deployment_history)


Client = Agentex

AsyncClient = AsyncAgentex
