from __future__ import annotations

import contextvars
from typing import TypeVar
from contextlib import asynccontextmanager
from collections.abc import Callable, Awaitable, AsyncIterator, AsyncGenerator

from agentex.lib.runtime.models import Credentials
from agentex.lib.runtime.resolver import CredentialResolver, PassthroughResolver

T = TypeVar("T")

_ctx_var_request_context: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
    "agentex_request_context", default=None
)

_default_resolver: CredentialResolver = PassthroughResolver()


def set_credential_resolver(resolver: CredentialResolver) -> None:
    """Configure the credential resolver used by runtime request context."""
    global _default_resolver
    _default_resolver = resolver


def get_credential_resolver() -> CredentialResolver:
    return _default_resolver


class RequestContext:
    """Per-request runtime context populated by FastACP on each inbound RPC."""

    def __init__(
        self,
        *,
        headers: dict[str, str],
        agent_id: str,
        resolver: CredentialResolver,
    ) -> None:
        self._headers = headers
        self._agent_id = agent_id
        self._resolver = resolver

    @classmethod
    def from_headers(
        cls,
        headers: dict[str, str],
        agent_id: str,
        resolver: CredentialResolver | None = None,
    ) -> RequestContext:
        return cls(
            headers=headers,
            agent_id=agent_id,
            resolver=resolver or get_credential_resolver(),
        )

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def get_credentials_for(self, target: str) -> Credentials:
        return await self._resolver.resolve(self._headers, self._agent_id, target)

    async def get_token(self, target: str = "sgp") -> str:
        """Return the raw credential value for a target (convenience wrapper)."""
        credentials = await self.get_credentials_for(target)
        return credentials.value


def current_request() -> RequestContext:
    """Return the active request context for the current RPC handler."""
    context = _ctx_var_request_context.get()
    if context is None:
        raise RuntimeError(
            "No active Agentex request context. Call current_request() only "
            "from code running inside an agent RPC handler."
        )
    return context


@asynccontextmanager
async def request_context_scope(
    headers: dict[str, str],
    agent_id: str,
    resolver: CredentialResolver | None = None,
) -> AsyncGenerator[RequestContext, None]:
    context = RequestContext.from_headers(headers, agent_id, resolver)
    token = _ctx_var_request_context.set(context)
    try:
        yield context
    finally:
        _ctx_var_request_context.reset(token)


async def run_with_request_context(
    headers: dict[str, str],
    agent_id: str,
    fn: Callable[[], Awaitable[T]],
    *,
    resolver: CredentialResolver | None = None,
) -> T:
    async with request_context_scope(headers, agent_id, resolver):
        return await fn()


async def wrap_async_generator_with_request_context(
    async_gen: AsyncIterator[T],
    headers: dict[str, str],
    agent_id: str,
    *,
    resolver: CredentialResolver | None = None,
) -> AsyncGenerator[T, None]:
    """Keep request context active while a streaming handler yields chunks."""
    async with request_context_scope(headers, agent_id, resolver):
        async for item in async_gen:
            yield item
