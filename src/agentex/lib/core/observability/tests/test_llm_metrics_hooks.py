"""Tests for ``agentex.lib.core.observability.llm_metrics_hooks``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import agentex.lib.core.observability.llm_metrics_hooks as hooks_module
from agentex.lib.core.observability.llm_metrics_hooks import (
    LLMMetricsHooks,
    record_llm_failure,
)


def _mock_response(
    *,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cached_tokens: int = 30,
    reasoning_tokens: int = 10,
) -> MagicMock:
    response = MagicMock()
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    response.usage.input_tokens_details.cached_tokens = cached_tokens
    response.usage.output_tokens_details.reasoning_tokens = reasoning_tokens
    return response


def _mock_agent(model: str = "gpt-5") -> MagicMock:
    agent = MagicMock()
    agent.model = model
    return agent


class TestLLMMetricsHooksOnLLMEnd:
    @pytest.mark.asyncio
    async def test_emits_success_request_counter(self, monkeypatch):
        m = MagicMock()
        monkeypatch.setattr(hooks_module, "get_llm_metrics", lambda: m)

        await LLMMetricsHooks().on_llm_end(
            context=MagicMock(),
            agent=_mock_agent("gpt-5"),
            response=_mock_response(),
        )

        m.requests.add.assert_called_once_with(1, {"model": "gpt-5", "status": "success"})

    @pytest.mark.asyncio
    async def test_emits_token_counters(self, monkeypatch):
        m = MagicMock()
        monkeypatch.setattr(hooks_module, "get_llm_metrics", lambda: m)

        await LLMMetricsHooks().on_llm_end(
            context=MagicMock(),
            agent=_mock_agent("gpt-5"),
            response=_mock_response(
                input_tokens=200,
                output_tokens=75,
                cached_tokens=50,
                reasoning_tokens=20,
            ),
        )

        attrs = {"model": "gpt-5"}
        m.input_tokens.add.assert_called_once_with(200, attrs)
        m.output_tokens.add.assert_called_once_with(75, attrs)
        m.cached_input_tokens.add.assert_called_once_with(50, attrs)
        m.reasoning_tokens.add.assert_called_once_with(20, attrs)

    @pytest.mark.asyncio
    async def test_zero_tokens_emit_zero_not_skip(self, monkeypatch):
        m = MagicMock()
        monkeypatch.setattr(hooks_module, "get_llm_metrics", lambda: m)

        await LLMMetricsHooks().on_llm_end(
            context=MagicMock(),
            agent=_mock_agent(),
            response=_mock_response(input_tokens=0, output_tokens=0, cached_tokens=0, reasoning_tokens=0),
        )

        m.input_tokens.add.assert_called_once_with(0, {"model": "gpt-5"})
        m.output_tokens.add.assert_called_once_with(0, {"model": "gpt-5"})

    @pytest.mark.asyncio
    async def test_unknown_model_falls_back(self, monkeypatch):
        m = MagicMock()
        monkeypatch.setattr(hooks_module, "get_llm_metrics", lambda: m)

        agent = MagicMock()
        agent.model = None

        await LLMMetricsHooks().on_llm_end(
            context=MagicMock(),
            agent=agent,
            response=_mock_response(),
        )

        m.requests.add.assert_called_once_with(1, {"model": "unknown", "status": "success"})

    @pytest.mark.asyncio
    async def test_swallows_exporter_failure(self, monkeypatch):
        m = MagicMock()
        m.requests.add.side_effect = RuntimeError("exporter exploded")
        monkeypatch.setattr(hooks_module, "get_llm_metrics", lambda: m)

        # Should not raise — caller's flow must not break on metric failure.
        await LLMMetricsHooks().on_llm_end(
            context=MagicMock(),
            agent=_mock_agent(),
            response=_mock_response(),
        )


class TestRecordLLMFailure:
    def test_emits_classified_status(self, monkeypatch):
        m = MagicMock()
        monkeypatch.setattr(hooks_module, "get_llm_metrics", lambda: m)

        class RateLimitError(Exception):
            pass

        record_llm_failure("gpt-5", RateLimitError())

        m.requests.add.assert_called_once_with(1, {"model": "gpt-5", "status": "rate_limit"})

    def test_swallows_exporter_failure(self, monkeypatch):
        m = MagicMock()
        m.requests.add.side_effect = RuntimeError("exporter exploded")
        monkeypatch.setattr(hooks_module, "get_llm_metrics", lambda: m)

        # Should not raise.
        record_llm_failure("gpt-5", Exception("upstream"))
