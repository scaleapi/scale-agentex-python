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
    ErrorBoundary,
    PlatformError,
    ApplicationError,
    CategorizedError,
    ExceptionMapping,
    ErrorClassifierConfig,
    TracebackOwnershipConfig,
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


def _synthetic_function(
    module_name: str,
    filename: str,
    body: str,
    **values: Any,
) -> Any:
    namespace = {"__name__": module_name, **values}
    exec(compile(f"def run():\n    {body}\n", filename, "exec"), namespace)
    return namespace["run"]


def _stack_config() -> ErrorClassifierConfig:
    return ErrorClassifierConfig(
        traceback_ownership=TracebackOwnershipConfig(
            application_module_prefixes=("customer_agent",),
            platform_module_prefixes=("agentex",),
            ignored_module_prefixes=("vendor_sdk",),
            application_file_roots=(),
            platform_file_roots=(),
            ignored_file_roots=(),
            infer_application_from_external_source=False,
        )
    )


def _record_raised(function: Any, *, config: ErrorClassifierConfig, **kwargs: Any) -> dict[str, Any]:
    span = _make_span()
    try:
        function()
    except Exception as exc:
        set_span_error(span, exc, classifier_config=config, **kwargs)
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

    def test_invalid_explicit_category_safely_wins_as_unknown(self):
        span = _make_span()
        set_span_error(span, PlatformError("boom"), error_category="not-a-category")
        error = get_span_error(span)
        assert error is not None
        assert error["category"] == "unknown"
        assert error["category_source"] == "explicit"
        assert error["category_reason"] == "invalid_explicit_category"

    @pytest.mark.parametrize(
        ("boundary", "category"),
        [
            (ErrorBoundary.AGENT_EXECUTION, "application"),
            (ErrorBoundary.AGENTEX_PLATFORM, "platform"),
        ],
    )
    def test_known_boundary_classifies_uncategorized_error(self, boundary, category):
        span = _make_span()
        set_span_error(span, RuntimeError("boom"), boundary=boundary)
        error = get_span_error(span)
        assert error is not None
        assert error["category"] == category
        assert error["category_source"] == "boundary"
        assert error["category_reason"] == f"agentex_boundary:{boundary.value}"

    def test_canonical_error_precedes_boundary(self):
        span = _make_span()
        set_span_error(span, PlatformError("boom"), boundary=ErrorBoundary.AGENT_EXECUTION)
        error = get_span_error(span)
        assert error is not None
        assert error["category"] == "platform"
        assert error["category_source"] == "categorized_error"

    def test_scoped_mapping_does_not_apply_globally(self):
        config = ErrorClassifierConfig([ExceptionMapping("provider-call", TimeoutError, "platform")])
        unscoped = _make_span()
        scoped = _make_span()

        set_span_error(unscoped, TimeoutError("boom"), classifier_config=config)
        set_span_error(scoped, TimeoutError("boom"), mapping_scope="provider-call", classifier_config=config)

        assert get_span_error(unscoped)["category"] == "unknown"  # type: ignore[index]
        error = get_span_error(scoped)
        assert error is not None
        assert error["category"] == "platform"
        assert error["category_source"] == "mapping"
        assert error["category_reason"].endswith("builtins.TimeoutError")

    def test_mapping_excludes_subclasses_by_default(self):
        class ProviderTimeout(TimeoutError):
            pass

        config = ErrorClassifierConfig([ExceptionMapping("provider-call", TimeoutError, "platform")])
        span = _make_span()
        set_span_error(span, ProviderTimeout("boom"), mapping_scope="provider-call", classifier_config=config)
        assert get_span_error(span)["category"] == "unknown"  # type: ignore[index]

    def test_mapping_can_explicitly_include_subclasses(self):
        class ProviderTimeout(TimeoutError):
            pass

        config = ErrorClassifierConfig(
            [ExceptionMapping("provider-call", TimeoutError, "platform", include_subclasses=True)]
        )
        span = _make_span()
        set_span_error(span, ProviderTimeout("boom"), mapping_scope="provider-call", classifier_config=config)
        assert get_span_error(span)["category"] == "platform"  # type: ignore[index]

    def test_boundary_precedes_mapping(self):
        config = ErrorClassifierConfig([ExceptionMapping("provider-call", TimeoutError, "platform")])
        span = _make_span()
        set_span_error(
            span,
            TimeoutError("boom"),
            boundary=ErrorBoundary.AGENT_EXECUTION,
            mapping_scope="provider-call",
            classifier_config=config,
        )
        error = get_span_error(span)
        assert error is not None
        assert error["category"] == "application"
        assert error["category_source"] == "boundary"

    def test_message_and_generic_exception_name_are_not_classification_signals(self):
        span = _make_span()
        set_span_error(span, TimeoutError("platform database unavailable"))
        assert get_span_error(span)["category"] == "unknown"  # type: ignore[index]

    def test_mapping_configuration_rejects_ambiguous_duplicates(self):
        with pytest.raises(ValueError, match="duplicate exception mapping"):
            ErrorClassifierConfig(
                [
                    ExceptionMapping("provider-call", TimeoutError, "platform"),
                    ExceptionMapping("provider-call", TimeoutError, "application"),
                ]
            )

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
# Automatic traceback inference
# ---------------------------------------------------------------------------


class TestStackTraceInference:
    def test_agentex_calling_user_code_is_application(self):
        user = _synthetic_function("customer_agent.tool", "/synthetic/app/tool.py", "raise RuntimeError('boom')")
        platform = _synthetic_function("agentex.lib.runner", "/synthetic/agentex/runner.py", "target()", target=user)

        error = _record_raised(platform, config=_stack_config())

        assert error["category"] == "application"
        assert error["category_source"] == "stack_trace"
        assert error["category_reason"] == "stack_rule:application_module"

    def test_user_calling_agentex_failure_is_platform(self):
        platform = _synthetic_function(
            "agentex.lib.runtime", "/synthetic/agentex/runtime.py", "raise RuntimeError('boom')"
        )
        user = _synthetic_function("customer_agent.main", "/synthetic/app/main.py", "target()", target=platform)

        error = _record_raised(user, config=_stack_config())

        assert error["category"] == "platform"
        assert error["category_reason"] == "stack_rule:platform_module"

    def test_dependency_failure_under_user_code_is_application(self):
        dependency = _synthetic_function(
            "vendor_sdk.transport", "/synthetic/vendor/transport.py", "raise RuntimeError('boom')"
        )
        user = _synthetic_function("customer_agent.main", "/synthetic/app/main.py", "target()", target=dependency)

        error = _record_raised(user, config=_stack_config())

        assert error["category"] == "application"
        assert error["category_reason"] == "stack_rule:application_module"

    def test_dependency_failure_under_agentex_is_platform(self):
        dependency = _synthetic_function(
            "vendor_sdk.transport", "/synthetic/vendor/transport.py", "raise RuntimeError('boom')"
        )
        platform = _synthetic_function(
            "agentex.lib.transport", "/synthetic/agentex/transport.py", "target()", target=dependency
        )

        error = _record_raised(platform, config=_stack_config())

        assert error["category"] == "platform"
        assert error["category_reason"] == "stack_rule:platform_module"

    def test_unresolvable_innermost_frame_is_unknown(self):
        unknown = _synthetic_function("obfuscated", "<obfuscated>", "raise RuntimeError('boom')")
        user = _synthetic_function("customer_agent.main", "/synthetic/app/main.py", "target()", target=unknown)

        error = _record_raised(user, config=_stack_config())

        assert error["category"] == "unknown"
        assert error["category_source"] == "fallback"
        assert error["category_reason"] == "stack_unresolvable_frame"

    def test_conflicting_frame_rules_are_unknown(self):
        config = ErrorClassifierConfig(
            traceback_ownership=TracebackOwnershipConfig(
                application_module_prefixes=("shared",),
                platform_module_prefixes=("shared",),
                ignored_file_roots=(),
                platform_file_roots=(),
                infer_application_from_external_source=False,
            )
        )
        shared = _synthetic_function("shared.runtime", "/synthetic/shared/runtime.py", "raise RuntimeError('boom')")

        error = _record_raised(shared, config=config)

        assert error["category"] == "unknown"
        assert error["category_reason"] == "stack_ambiguous_owned_frame"

    def test_explicit_category_overrides_real_traceback(self):
        platform = _synthetic_function(
            "agentex.lib.runtime", "/synthetic/agentex/runtime.py", "raise RuntimeError('boom')"
        )

        error = _record_raised(platform, config=_stack_config(), error_category="application")

        assert error["category"] == "application"
        assert error["category_source"] == "explicit"

    def test_canonical_error_overrides_real_traceback(self):
        user = _synthetic_function(
            "customer_agent.main",
            "/synthetic/app/main.py",
            "raise error_type('boom')",
            error_type=PlatformError,
        )

        error = _record_raised(user, config=_stack_config())

        assert error["category"] == "platform"
        assert error["category_source"] == "categorized_error"

    def test_stack_trace_precedes_boundary_and_mapping(self):
        config = ErrorClassifierConfig(
            [ExceptionMapping("provider-call", RuntimeError, "platform")],
            traceback_ownership=_stack_config().traceback_ownership,
        )
        user = _synthetic_function("customer_agent.main", "/synthetic/app/main.py", "raise RuntimeError('boom')")

        error = _record_raised(
            user,
            config=config,
            boundary=ErrorBoundary.AGENTEX_PLATFORM,
            mapping_scope="provider-call",
        )

        assert error["category"] == "application"
        assert error["category_source"] == "stack_trace"


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
            "category_reason": "stack_rule:external_source_file",
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
            "category_reason": "stack_rule:external_source_file",
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
