"""Tests for ``agentex.lib.core.observability.llm_metrics``."""

from __future__ import annotations

import agentex.lib.core.observability.llm_metrics as llm_metrics
from agentex.lib.core.observability.llm_metrics import (
    LLMMetrics,
    classify_status,
    get_llm_metrics,
)


class TestClassifyStatus:
    def test_none_is_success(self):
        assert classify_status(None) == "success"

    def test_rate_limit(self):
        class RateLimitError(Exception):
            pass

        assert classify_status(RateLimitError()) == "rate_limit"

    def test_timeout(self):
        class APITimeoutError(Exception):
            pass

        assert classify_status(APITimeoutError()) == "timeout"

    def test_server_error(self):
        class InternalServerError(Exception):
            pass

        assert classify_status(InternalServerError()) == "server_error"

        class ServiceUnavailable(Exception):
            pass

        assert classify_status(ServiceUnavailable()) == "server_error"

    def test_network_error(self):
        class APIConnectionError(Exception):
            pass

        assert classify_status(APIConnectionError()) == "network_error"

    def test_client_error(self):
        for cls_name in ("BadRequestError", "AuthenticationError", "PermissionError"):
            cls = type(cls_name, (Exception,), {})
            assert classify_status(cls()) == "client_error"

    def test_unknown_falls_back(self):
        class WeirdProviderException(Exception):
            pass

        assert classify_status(WeirdProviderException()) == "other_error"


class TestGetLLMMetrics:
    def test_returns_llm_metrics_instance(self, monkeypatch):
        monkeypatch.setattr(llm_metrics, "_llm_metrics", None)
        m = get_llm_metrics()
        assert isinstance(m, LLMMetrics)

    def test_singleton_returns_same_instance(self, monkeypatch):
        monkeypatch.setattr(llm_metrics, "_llm_metrics", None)
        first = get_llm_metrics()
        second = get_llm_metrics()
        assert first is second

    def test_instruments_exist(self, monkeypatch):
        monkeypatch.setattr(llm_metrics, "_llm_metrics", None)
        m = get_llm_metrics()
        for name in (
            "requests",
            "ttft_ms",
            "ttat_ms",
            "tps",
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
        ):
            assert hasattr(m, name), f"missing instrument: {name}"
