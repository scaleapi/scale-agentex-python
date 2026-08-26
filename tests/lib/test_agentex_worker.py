import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAgentexWorker:
    """Tests for AgentexWorker initialization and configuration."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Cleanup environment variables after each test."""
        yield
        # Clean up HEALTH_CHECK_PORT if it was set during test
        os.environ.pop("HEALTH_CHECK_PORT", None)

    def test_worker_init_uses_default_health_check_port(self):
        """Test that worker uses default health_check_port of 80 when not provided."""
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        # Ensure HEALTH_CHECK_PORT is not in environment
        os.environ.pop("HEALTH_CHECK_PORT", None)

        # Mock EnvironmentVariables.refresh to avoid loading .env files
        with patch("agentex.lib.core.temporal.workers.worker.EnvironmentVariables") as mock_env_vars:
            mock_instance = mock_env_vars.refresh.return_value
            mock_instance.HEALTH_CHECK_PORT = 80

            worker = AgentexWorker(task_queue="test-queue")

            assert worker.health_check_port == 80, "Worker should use default health_check_port of 80"

    def test_worker_init_with_explicit_health_check_port(self):
        """Test that worker uses explicit health_check_port parameter when provided."""
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        worker = AgentexWorker(task_queue="test-queue", health_check_port=8080)

        assert worker.health_check_port == 8080, "Worker should use explicitly provided health_check_port"

    def test_worker_init_explicit_port_overrides_environment(self):
        """Test that explicit health_check_port parameter overrides environment variable."""
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        # Set environment variable
        os.environ["HEALTH_CHECK_PORT"] = "9000"

        worker = AgentexWorker(task_queue="test-queue", health_check_port=8080)

        assert worker.health_check_port == 8080, "Explicit parameter should override environment variable"

    @pytest.mark.parametrize(
        "env_port,expected_port",
        [
            (None, 80),  # No env var, should use default
            ("8080", 8080),  # Env var set, should use it
            ("443", 443),  # Different port
        ],
    )
    def test_worker_init_respects_environment_variable(self, env_port, expected_port):
        """Test that worker respects HEALTH_CHECK_PORT from EnvironmentVariables."""
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        # Mock EnvironmentVariables.refresh to return expected port
        with patch("agentex.lib.core.temporal.workers.worker.EnvironmentVariables") as mock_env_vars:
            mock_instance = mock_env_vars.refresh.return_value
            mock_instance.HEALTH_CHECK_PORT = expected_port

            worker = AgentexWorker(task_queue="test-queue")

            assert worker.health_check_port == expected_port, f"Worker should use health_check_port {expected_port}"

    def test_worker_init_basic_attributes(self):
        """Test that worker initializes with correct basic attributes."""
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        worker = AgentexWorker(
            task_queue="test-queue",
            max_workers=20,
            max_concurrent_activities=15,
            health_check_port=8080,
        )

        assert worker.task_queue == "test-queue"
        assert worker.max_workers == 20
        assert worker.max_concurrent_activities == 15
        assert worker.health_check_port == 8080
        assert worker.health_check_server_running is False
        assert worker.healthy is False
        assert worker.plugins == []

    def test_worker_stores_metrics_params(self):
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        worker = AgentexWorker(
            task_queue="test-queue",
            health_check_port=8080,
            metrics_url="http://example.com/v1/metrics",
            metrics_headers={"Authorization": "Api-Token tok"},
            metrics_use_http=True,
            metrics_temporality_delta=True,
        )

        assert worker.metrics_url == "http://example.com/v1/metrics"
        assert worker.metrics_headers == {"Authorization": "Api-Token tok"}
        assert worker.metrics_use_http is True
        assert worker.metrics_temporality_delta is True

    def test_worker_metrics_params_default_to_none_and_false(self):
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        worker = AgentexWorker(task_queue="test-queue", health_check_port=8080)

        assert worker.metrics_url is None
        assert worker.metrics_headers is None
        assert worker.metrics_use_http is False
        assert worker.metrics_temporality_delta is False


class TestGetTemporalClientMetricsConfig:
    """Tests that metrics params reach OpenTelemetryConfig correctly."""

    async def test_metrics_params_reach_otel_config(self):
        from temporalio.client import Client
        from temporalio.runtime import OpenTelemetryMetricTemporality

        from agentex.lib.core.temporal.workers.worker import get_temporal_client

        with patch.object(Client, "connect", new=AsyncMock(return_value=MagicMock())), \
                patch("agentex.lib.core.temporal.workers.worker.Runtime"), \
                patch("agentex.lib.core.temporal.workers.worker.TelemetryConfig"), \
                patch("agentex.lib.core.temporal.workers.worker.OpenTelemetryConfig") as mock_otel:
            await get_temporal_client(
                "localhost:7233",
                metrics_url="http://example.com/v1/metrics",
                metrics_headers={"Authorization": "Api-Token tok"},
                metrics_use_http=True,
                metrics_temporality_delta=True,
            )

        mock_otel.assert_called_once_with(
            url="http://example.com/v1/metrics",
            headers={"Authorization": "Api-Token tok"},
            http=True,
            metric_temporality=OpenTelemetryMetricTemporality.DELTA,
        )

    async def test_delta_false_maps_to_cumulative(self):
        from temporalio.client import Client
        from temporalio.runtime import OpenTelemetryMetricTemporality

        from agentex.lib.core.temporal.workers.worker import get_temporal_client

        with patch.object(Client, "connect", new=AsyncMock(return_value=MagicMock())), \
                patch("agentex.lib.core.temporal.workers.worker.Runtime"), \
                patch("agentex.lib.core.temporal.workers.worker.TelemetryConfig"), \
                patch("agentex.lib.core.temporal.workers.worker.OpenTelemetryConfig") as mock_otel:
            await get_temporal_client(
                "localhost:7233",
                metrics_url="http://example.com/v1/metrics",
                metrics_temporality_delta=False,
            )

        _, kwargs = mock_otel.call_args
        assert kwargs["metric_temporality"] == OpenTelemetryMetricTemporality.CUMULATIVE

    async def test_none_headers_defaults_to_empty_dict(self):
        from temporalio.client import Client

        from agentex.lib.core.temporal.workers.worker import get_temporal_client

        with patch.object(Client, "connect", new=AsyncMock(return_value=MagicMock())), \
                patch("agentex.lib.core.temporal.workers.worker.Runtime"), \
                patch("agentex.lib.core.temporal.workers.worker.TelemetryConfig"), \
                patch("agentex.lib.core.temporal.workers.worker.OpenTelemetryConfig") as mock_otel:
            await get_temporal_client(
                "localhost:7233",
                metrics_url="http://example.com/v1/metrics",
            )

        _, kwargs = mock_otel.call_args
        assert kwargs["headers"] == {}

    async def test_no_metrics_url_skips_runtime(self):
        from temporalio.client import Client

        from agentex.lib.core.temporal.workers.worker import get_temporal_client

        with patch.object(Client, "connect", new=AsyncMock(return_value=MagicMock())), \
                patch("agentex.lib.core.temporal.workers.worker.Runtime") as mock_runtime:
            await get_temporal_client("localhost:7233")

        mock_runtime.assert_not_called()
