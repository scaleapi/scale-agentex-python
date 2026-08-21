from __future__ import annotations

import uuid
from typing import Any
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from scale_gp_beta.lib.tracing import (
    PlatformError as SGPPlatformError,
    ApplicationError as SGPApplicationError,
    CategorizedError as SGPCategorizedError,
)

from agentex.types.span import Span
from agentex.lib.core.tracing.trace import Trace, AsyncTrace
from agentex.lib.core.tracing.span_error import (
    SPAN_ERROR_KEY,
    ERROR_CLASSIFIER_VERSION,
    PlatformError,
    ApplicationError,
    CategorizedError,
    get_span_error,
    set_span_error,
)

PROCESSOR_MODULE = "agentex.lib.core.tracing.processors.sgp_tracing_processor"


def _make_span(data=None) -> Span:
    return Span(
        id=str(uuid.uuid4()),
        name="test-span",
        start_time=datetime.now(UTC),
        trace_id="trace-1",
        data=data,
    )


def _synthetic_function(module_name: str, filename: str, body: str, **values: Any) -> Any:
    namespace = {"__name__": module_name, **values}
    exec(compile(f"def run():\n    {body}\n", filename, "exec"), namespace)
    return namespace["run"]


def _record_synthetic(function: Any, *, innermost_only: bool = False) -> dict[str, Any]:
    span = _make_span()
    try:
        function()
    except Exception as exc:
        if innermost_only:
            traceback = exc.__traceback__
            assert traceback is not None
            while traceback.tb_next is not None:
                traceback = traceback.tb_next
            exc = exc.with_traceback(traceback)
        set_span_error(span, exc)
    error = get_span_error(span)
    assert error is not None
    return error


# ---------------------------------------------------------------------------
# Helpers: set_span_error / get_span_error
# ---------------------------------------------------------------------------


class TestSpanErrorHelpers:
    def test_uses_canonical_sgp_error_types(self):
        assert CategorizedError is SGPCategorizedError
        assert ApplicationError is SGPApplicationError
        assert PlatformError is SGPPlatformError

    def test_set_then_get_on_none_data(self):
        span = _make_span(data=None)
        set_span_error(span, ValueError("boom"))
        assert get_span_error(span) == {
            "type": "ValueError",
            "message": "boom",
            "category": "unknown",
            "category_source": "fallback",
            "classifier_version": ERROR_CLASSIFIER_VERSION,
            "category_reason": "stack_no_traceback",
        }
        assert isinstance(span.data, dict)
        assert span.data[SPAN_ERROR_KEY] == get_span_error(span)

    def test_set_uses_explicit_exception_category(self):
        span = _make_span(data=None)
        set_span_error(span, PlatformError("unavailable"))
        assert get_span_error(span) == {
            "type": "PlatformError",
            "message": "unavailable",
            "category": "platform",
            "category_source": "categorized_error",
            "classifier_version": ERROR_CLASSIFIER_VERSION,
            "category_reason": "canonical_categorized_error",
        }

    def test_explicit_category_takes_precedence(self):
        span = _make_span(data=None)
        set_span_error(span, PlatformError("bad input"), error_category="application")
        error = get_span_error(span)
        assert error is not None
        assert error["category"] == "application"
        assert error["category_source"] == "explicit"

    def test_set_uses_application_error_category(self):
        span = _make_span(data=None)
        set_span_error(span, ApplicationError("bad input"))
        assert get_span_error(span)["category"] == "application"  # type: ignore[index]

    def test_bare_exception_attribute_does_not_opt_in(self):
        class ImplicitlyCategorizedError(RuntimeError):
            error_category = "platform"

        span = _make_span(data=None)
        set_span_error(span, ImplicitlyCategorizedError("boom"))
        assert get_span_error(span)["category"] == "unknown"  # type: ignore[index]

    def test_generic_agentex_wrapper_around_user_failure_is_application(self):
        application = _synthetic_function(
            "customer_agent.tool",
            "/synthetic/application/tool.py",
            "raise RuntimeError('boom')",
        )
        wrapper = _synthetic_function(
            "agentex.lib.core.temporal.workflows.workflow",
            "/synthetic/agentex/workflow.py",
            "target()",
            target=application,
        )

        error = _record_synthetic(wrapper)

        assert error["category"] == "application"
        assert error["category_source"] == "stack_trace"
        assert error["category_reason"] == "stack_rule:unowned_absolute_source"

    def test_application_database_failure_is_application(self):
        driver = _synthetic_function(
            "sqlalchemy.engine",
            "/venv/site-packages/sqlalchemy/engine.py",
            "raise RuntimeError('db failed')",
        )
        application = _synthetic_function(
            "customer_agent.main",
            "/synthetic/application/main.py",
            "query()",
            query=driver,
        )

        assert _record_synthetic(application)["category"] == "application"

    def test_managed_stream_database_failure_is_platform(self):
        driver = _synthetic_function(
            "redis.asyncio.client",
            "/venv/site-packages/redis/client.py",
            "raise RuntimeError('db failed')",
        )
        managed_store = _synthetic_function(
            "agentex.lib.core.adapters.streams.adapter_redis",
            "/synthetic/agentex/adapter_redis.py",
            "query()",
            query=driver,
        )

        assert _record_synthetic(managed_store)["category"] == "platform"

    def test_application_validation_inside_platform_operation_is_application(self):
        validation = _synthetic_function(
            "customer_agent.query",
            "/synthetic/application/query.py",
            "raise ValueError('invalid configuration')",
        )
        managed_store = _synthetic_function(
            "agentex.lib.core.adapters.streams.adapter_redis",
            "/synthetic/agentex/adapter_redis.py",
            "validate()",
            validate=validation,
        )

        assert _record_synthetic(managed_store)["category"] == "application"

    def test_driver_only_database_failure_is_unknown(self):
        driver = _synthetic_function(
            "pyodbc",
            "/venv/site-packages/pyodbc.py",
            "raise RuntimeError('db failed')",
        )

        error = _record_synthetic(driver, innermost_only=True)

        assert error["category"] == "unknown"
        assert error["category_reason"] == "stack_no_owned_frame"

    def test_nested_wrapper_dependency_propagation_uses_application(self):
        driver = _synthetic_function(
            "sqlalchemy.engine",
            "/venv/site-packages/sqlalchemy/engine.py",
            "raise RuntimeError('db failed')",
        )
        application = _synthetic_function(
            "customer_agent.repository",
            "/synthetic/application/repository.py",
            "query()",
            query=driver,
        )
        wrapper = _synthetic_function(
            "agentex.lib.core.temporal.activities.activity_helpers",
            "/synthetic/agentex/activity_helpers.py",
            "target()",
            target=application,
        )

        assert _record_synthetic(wrapper)["category"] == "application"

    def test_set_preserves_existing_dict_keys(self):
        span = _make_span(data={"__span_type__": "LLM"})
        set_span_error(span, RuntimeError("nope"))
        assert isinstance(span.data, dict)
        assert span.data["__span_type__"] == "LLM"
        err = get_span_error(span)
        assert err is not None
        assert err["type"] == "RuntimeError"

    def test_get_returns_none_when_no_error(self):
        assert get_span_error(_make_span(data={"foo": "bar"})) is None
        assert get_span_error(_make_span(data=None)) is None

    def test_set_is_noop_on_list_data(self):
        span = _make_span(data=[{"a": 1}])
        set_span_error(span, ValueError("boom"))
        # list-shaped data is left untouched (mirrors _add_source_to_span)
        assert span.data == [{"a": 1}]
        assert get_span_error(span) is None


# ---------------------------------------------------------------------------
# Capture: the context managers record body exceptions onto the span
# ---------------------------------------------------------------------------


class TestContextManagerCapture:
    def test_sync_span_records_error_and_reraises(self):
        trace = Trace(processors=[], client=MagicMock(), trace_id="t1")
        captured = {}
        with pytest.raises(ValueError, match="boom"):
            with trace.span("op") as span:
                captured["span"] = span
                raise ValueError("boom")
        err = get_span_error(captured["span"])
        assert err == {
            "type": "ValueError",
            "message": "boom",
            "category": "application",
            "category_source": "stack_trace",
            "classifier_version": ERROR_CLASSIFIER_VERSION,
            "category_reason": "stack_rule:unowned_absolute_source",
        }

    def test_sync_span_success_has_no_error(self):
        trace = Trace(processors=[], client=MagicMock(), trace_id="t1")
        with trace.span("op") as span:
            pass
        assert get_span_error(span) is None

    @pytest.mark.asyncio
    async def test_async_span_records_error_and_reraises(self):
        trace = AsyncTrace(processors=[], client=MagicMock(), trace_id="t1")
        captured = {}
        with pytest.raises(RuntimeError, match="kaboom"):
            async with trace.span("op") as span:
                captured["span"] = span
                raise RuntimeError("kaboom")
        err = get_span_error(captured["span"])
        assert err == {
            "type": "RuntimeError",
            "message": "kaboom",
            "category": "application",
            "category_source": "stack_trace",
            "classifier_version": ERROR_CLASSIFIER_VERSION,
            "category_reason": "stack_rule:unowned_absolute_source",
        }


# ---------------------------------------------------------------------------
# Map: _build_sgp_span translates the recorded error into SGP status=ERROR
# ---------------------------------------------------------------------------


class _FakeSGPSpan:
    def __init__(self, metadata: dict[str, Any] | None) -> None:
        self.status = "SUCCESS"
        self.metadata: dict[str, Any] = metadata if metadata is not None else {}
        self.start_time = None

    def set_error(
        self,
        error_type: str | None = None,
        error_message: str | None = None,
        exception: BaseException | None = None,  # noqa: ARG002
    ) -> None:
        self.status = "ERROR"
        self.metadata["error"] = True
        self.metadata["error_type"] = error_type
        self.metadata["error_message"] = error_message


def _fake_create_span(**kwargs: Any) -> _FakeSGPSpan:
    return _FakeSGPSpan(kwargs.get("metadata"))


class TestBuildSGPSpanMapping:
    @staticmethod
    def _env():
        return MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)

    def test_error_maps_to_status_error(self):
        from agentex.lib.core.tracing.processors.sgp_tracing_processor import _build_sgp_span

        span = _make_span(
            data={
                SPAN_ERROR_KEY: {
                    "type": "ValueError",
                    "message": "boom",
                    "category": "application",
                    "category_source": "stack_trace",
                    "classifier_version": ERROR_CLASSIFIER_VERSION,
                    "category_reason": "stack_rule:application_module",
                }
            }
        )
        with patch(f"{PROCESSOR_MODULE}.create_span", side_effect=_fake_create_span):
            sgp_span = _build_sgp_span(span, self._env())

        assert sgp_span.status == "ERROR"
        assert sgp_span.metadata["error"] is True
        assert sgp_span.metadata["error_type"] == "ValueError"
        assert sgp_span.metadata["error_message"] == "boom"
        assert sgp_span.metadata["error_category"] == "application"
        assert sgp_span.metadata["error_category_source"] == "stack_trace"
        assert sgp_span.metadata["error_classifier_version"] == ERROR_CLASSIFIER_VERSION
        assert sgp_span.metadata["error_category_reason"] == "stack_rule:application_module"

    def test_no_error_leaves_status_success(self):
        from agentex.lib.core.tracing.processors.sgp_tracing_processor import _build_sgp_span

        span = _make_span(data={"__span_type__": "LLM"})
        with patch(f"{PROCESSOR_MODULE}.create_span", side_effect=_fake_create_span):
            sgp_span = _build_sgp_span(span, self._env())

        assert sgp_span.status == "SUCCESS"
        assert "error" not in sgp_span.metadata
