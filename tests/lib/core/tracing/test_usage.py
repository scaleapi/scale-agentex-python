from __future__ import annotations

from types import SimpleNamespace

from agentex.lib.core.tracing.usage import (
    usage_from_counts,
    validate_usage_blob,
    usage_from_openai_response_usage,
)


class TestUsageFromCounts:
    def test_all_fields(self):
        assert usage_from_counts(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=20,
            reasoning_tokens=10,
            cost_usd=0.0123,
        ) == {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "cached_input_tokens": 20,
            "reasoning_tokens": 10,
            "cost_usd": 0.0123,
        }

    def test_none_values_omitted(self):
        assert usage_from_counts(input_tokens=100, output_tokens=50) == {
            "input_tokens": 100,
            "output_tokens": 50,
        }

    def test_explicit_zeros_kept(self):
        assert usage_from_counts(input_tokens=0, output_tokens=0) == {
            "input_tokens": 0,
            "output_tokens": 0,
        }


class TestUsageFromOpenAIResponseUsage:
    def test_none_returns_none(self):
        assert usage_from_openai_response_usage(None) is None

    def test_object_without_token_fields_returns_none(self):
        assert usage_from_openai_response_usage(SimpleNamespace(requests=1)) is None

    def test_full_usage_with_details(self):
        usage = SimpleNamespace(
            input_tokens=120,
            output_tokens=80,
            total_tokens=200,
            input_tokens_details=SimpleNamespace(cached_tokens=30),
            output_tokens_details=SimpleNamespace(reasoning_tokens=40),
        )
        assert usage_from_openai_response_usage(usage) == {
            "input_tokens": 120,
            "output_tokens": 80,
            "total_tokens": 200,
            "cached_input_tokens": 30,
            "reasoning_tokens": 40,
        }

    def test_usage_without_details(self):
        usage = SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            input_tokens_details=None,
            output_tokens_details=None,
        )
        assert usage_from_openai_response_usage(usage) == {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }


class TestValidateUsageBlob:
    def test_passthrough_recognized_keys(self):
        blob = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        assert validate_usage_blob(blob) == blob

    def test_warns_on_unrecognized_keys(self, caplog):
        with caplog.at_level("WARNING"):
            result = validate_usage_blob({"inputTokens": 10})
        assert result == {"inputTokens": 10}
        assert any("no recognized token keys" in message for message in caplog.messages)
