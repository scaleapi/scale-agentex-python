"""Unit tests for handing the ACP request id to the observability pipeline.

``request_id`` used to reach the logs through exactly one writer: ``CustomJSONFormatter``
on the handler ``make_logger`` attaches to each module's own logger. That handler is
taken off once a logs pipeline owns the root logger, because it was printing a second,
ungoverned copy of every record — so the id has to be handed over, or it is simply lost.
Measured on dbt-assistant running 0.27.0b1, ``request_id`` was on 5.2% of log lines,
which were exactly the ungoverned copies.

The hand-over target is sgp-obs' shared correlation context (``sgp_obs.context``:
``bind(**fields) -> Token``, ``reset(token)``, ``current()``), stubbed here because
sgp-obs is an optional install and is deliberately not a dependency of this package.
"""

from __future__ import annotations

from typing import Any
from contextvars import ContextVar

import pytest

from agentex.lib.utils.logging import ctx_var_request_id
from agentex.lib.sdk.fastacp.base import base_acp_server
from agentex.lib.sdk.fastacp.base.base_acp_server import (
    RequestIDMiddleware,
    _bind_request_id_for_telemetry,
    _unbind_request_id_for_telemetry,
)


class StubObsContext:
    """The shape of ``sgp_obs.context`` that this SDK uses, over a real ContextVar so
    "was the id in scope while the request ran?" is a real question."""

    def __init__(self) -> None:
        self._var: ContextVar[str | None] = ContextVar("stub_request_id", default=None)
        self.binds: list[dict[str, Any]] = []
        self.resets = 0

    def bind(self, **fields: Any) -> object:
        self.binds.append(fields)
        return self._var.set(fields.get("request_id"))

    def reset(self, token: Any) -> None:
        self.resets += 1
        self._var.reset(token)

    def current(self) -> str | None:
        return self._var.get()


@pytest.fixture
def obs(monkeypatch: pytest.MonkeyPatch) -> StubObsContext:
    stub = StubObsContext()
    # The memo is the seam: the helpers resolve `sgp_obs.context` once per process.
    monkeypatch.setattr(base_acp_server, "_obs_context_module", stub)
    return stub


def test_the_request_id_is_bound_for_the_pipeline(obs: StubObsContext) -> None:
    token = _bind_request_id_for_telemetry("req-abc")
    try:
        assert obs.binds == [{"request_id": "req-abc"}]
        assert obs.current() == "req-abc"
    finally:
        _unbind_request_id_for_telemetry(token)


def test_it_is_unbound_again(obs: StubObsContext) -> None:
    _unbind_request_id_for_telemetry(_bind_request_id_for_telemetry("req-abc"))
    assert obs.resets == 1
    assert obs.current() is None


def test_an_absent_sgp_obs_is_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """The normal case for an agent that has not installed it."""
    monkeypatch.setattr(base_acp_server, "_obs_context_module", None)
    assert _bind_request_id_for_telemetry("req-abc") is None
    _unbind_request_id_for_telemetry(None)  # must be safe


def test_a_raising_bind_does_not_break_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """``bind`` rejects unknown field names, so a future rename must degrade to no
    correlation rather than to a failed request."""

    class Raising:
        def bind(self, **_fields: Any) -> object:
            raise TypeError("unexpected keyword argument")

        def reset(self, _token: Any) -> None:
            raise AssertionError("nothing to reset")

    monkeypatch.setattr(base_acp_server, "_obs_context_module", Raising())
    assert _bind_request_id_for_telemetry("req-abc") is None


@pytest.mark.asyncio
async def test_the_middleware_binds_the_same_id_it_gives_application_code(
    obs: StubObsContext,
) -> None:
    """One generator for the value: the id in the logs is the id the SDK's own
    contextvar hands to the agent, and the id ``x-request-id`` carried in."""
    seen: dict[str, Any] = {}

    async def app(_scope: Any, _receive: Any, _send: Any) -> None:
        seen["sdk"] = ctx_var_request_id.get(None)
        seen["obs"] = obs.current()

    scope = {"type": "http", "headers": [(b"x-request-id", b"req-from-the-gateway")]}
    await RequestIDMiddleware(app)(scope, None, None)  # type: ignore[arg-type]

    assert seen["obs"] == "req-from-the-gateway"
    assert seen["sdk"] == seen["obs"]
    # Bound for the request only, so a later record cannot inherit a stale id.
    assert obs.current() is None
    assert obs.resets == 1


@pytest.mark.asyncio
async def test_a_generated_id_is_bound_when_the_header_is_absent(obs: StubObsContext) -> None:
    seen: dict[str, Any] = {}

    async def app(_scope: Any, _receive: Any, _send: Any) -> None:
        seen["obs"] = obs.current()

    await RequestIDMiddleware(app)({"type": "http", "headers": []}, None, None)  # type: ignore[arg-type]
    assert seen["obs"]


@pytest.mark.asyncio
async def test_a_non_http_scope_binds_nothing(obs: StubObsContext) -> None:
    """Lifespan and websocket scopes have no request id to bind."""

    async def app(_scope: Any, _receive: Any, _send: Any) -> None:
        return None

    await RequestIDMiddleware(app)({"type": "lifespan"}, None, None)  # type: ignore[arg-type]
    assert obs.binds == []
    assert obs.resets == 0


@pytest.mark.asyncio
async def test_it_is_unbound_even_when_the_request_raises(obs: StubObsContext) -> None:
    async def app(_scope: Any, _receive: Any, _send: Any) -> None:
        raise RuntimeError("handler blew up")

    with pytest.raises(RuntimeError):
        await RequestIDMiddleware(app)({"type": "http", "headers": []}, None, None)  # type: ignore[arg-type]
    assert obs.resets == 1
    assert obs.current() is None
