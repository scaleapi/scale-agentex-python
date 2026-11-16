"""Tests for the ADK ``TracingModule.span`` / ``turn_span`` error-status behavior.

Regression coverage for the "false green" bug: agents open spans through the ADK
context manager (``adk.tracing.span`` / ``turn_span``), which is the *only* span
path they use. Before the fix, a failing step still closed its span green because
the CM never recorded the exception. These tests assert that:

  - a body exception is recorded on the span (``set_span_error`` -> ``data["__error__"]``),
  - the ORIGINAL app exception always propagates unchanged,
  - ``end_span`` sees the span *with* the error already set (except-before-finally),
  - obs bookkeeping never breaks the app path (if ``set_span_error`` itself raises,
    the app exception still propagates),
  - the success path records no error,
  - a falsy ``trace_id`` is a pure no-op (no start/end, yields ``None``),
  - ``turn_span`` inherits all of the above since it delegates to ``span``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agentex.types.span import Span
from agentex.lib.adk._modules.tracing import TracingModule
from agentex.lib.core.tracing.span_error import ERROR_CLASSIFIER_VERSION, get_span_error


def _make_module() -> tuple[TracingModule, Span, AsyncMock]:
    """A TracingModule with start_span/end_span stubbed to avoid any network.

    start_span returns a fresh Span; end_span is an AsyncMock so tests can
    inspect the span (and its recorded error) as end_span actually saw it.
    """
    module = TracingModule()
    span = Span(id="span-1", name="step", start_time=1.0, trace_id="trace-1")
    module.start_span = AsyncMock(return_value=span)  # type: ignore[method-assign]
    module.end_span = AsyncMock(return_value=span)  # type: ignore[method-assign]
    return module, span, module.end_span  # type: ignore[return-value]


async def test_span_records_error_and_reraises() -> None:
    module, span, end_span = _make_module()

    with pytest.raises(ValueError, match="boom"):
        async with module.span(trace_id="trace-1", name="step") as yielded:
            assert yielded is span
            raise ValueError("boom")

    error = get_span_error(span)
    assert error == {
        "type": "ValueError",
        "message": "boom",
        "category": "application",
        "category_source": "stack_trace",
        "classifier_version": ERROR_CLASSIFIER_VERSION,
        "category_reason": "stack_rule:unowned_absolute_source",
    }

    # end_span still ran (finally) and saw the span with the error already set,
    # so the failure is what gets persisted -- not a false green.
    end_span.assert_awaited_once()
    persisted_span = end_span.await_args.kwargs["span"]
    assert get_span_error(persisted_span) == {
        "type": "ValueError",
        "message": "boom",
        "category": "application",
        "category_source": "stack_trace",
        "classifier_version": ERROR_CLASSIFIER_VERSION,
        "category_reason": "stack_rule:unowned_absolute_source",
    }


async def test_span_success_records_no_error() -> None:
    module, span, end_span = _make_module()

    async with module.span(trace_id="trace-1", name="step") as yielded:
        assert yielded is span

    assert get_span_error(span) is None
    end_span.assert_awaited_once()


async def test_span_obs_failure_does_not_shadow_app_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """If set_span_error itself blows up, the app's exception must still surface."""
    module, span, end_span = _make_module()

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("set_span_error is broken")

    monkeypatch.setattr("agentex.lib.adk._modules.tracing.set_span_error", _boom)

    # The ORIGINAL ValueError propagates, not the RuntimeError from obs code.
    with pytest.raises(ValueError, match="boom"):
        async with module.span(trace_id="trace-1", name="step"):
            raise ValueError("boom")

    # The span still gets closed despite the obs hiccup.
    end_span.assert_awaited_once()


async def test_span_noop_when_trace_id_falsy() -> None:
    module, _span, end_span = _make_module()

    async with module.span(trace_id="", name="step") as yielded:
        assert yielded is None

    module.start_span.assert_not_awaited()  # type: ignore[attr-defined]
    end_span.assert_not_awaited()


async def test_turn_span_records_error_and_reraises() -> None:
    """turn_span delegates to span(), so it must record errors too."""
    module, span, end_span = _make_module()

    with pytest.raises(ValueError, match="boom"):
        async with module.turn_span(trace_id="trace-1", name="turn") as turn:
            assert turn.span is span
            raise ValueError("boom")

    assert get_span_error(span) == {
        "type": "ValueError",
        "message": "boom",
        "category": "application",
        "category_source": "stack_trace",
        "classifier_version": ERROR_CLASSIFIER_VERSION,
        "category_reason": "stack_rule:unowned_absolute_source",
    }
    end_span.assert_awaited_once()
