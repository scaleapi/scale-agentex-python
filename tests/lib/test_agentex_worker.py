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


class TestAgentexWorkerAgentCard:
    """Tests that AgentexWorker publishes an optional AgentCard through the
    existing automatic registration lifecycle."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        yield
        for key in ("AGENT_ID", "AGENT_NAME", "AGENT_API_KEY"):
            os.environ.pop(key, None)

    @staticmethod
    def _env_vars_mock():
        env = MagicMock()
        env.AGENTEX_BASE_URL = "http://agentex.test"
        env.ACP_URL = "http://agent.test"
        env.ACP_PORT = 8000
        env.AGENT_DESCRIPTION = "test description"
        env.AGENT_NAME = "test-agent"
        env.ACP_TYPE = "agentic"
        env.AUTH_PRINCIPAL_B64 = None
        env.AGENTEX_DEPLOYMENT_ID = None
        env.AGENT_ID = None
        env.AGENT_INPUT_TYPE = None
        return env

    @staticmethod
    def _httpx_client_mock(captured_payloads):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "id": "agent-id",
            "name": "test-agent",
            "agent_api_key": "api-key",
        }

        async def post(url, json=None, timeout=None):  # noqa: ARG001
            captured_payloads.append(json)
            return response

        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(side_effect=post)))
        client.__aexit__ = AsyncMock(return_value=False)
        return MagicMock(return_value=client)

    def test_worker_agent_card_defaults_to_none(self):
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        worker = AgentexWorker(task_queue="test-queue", health_check_port=8080)

        assert worker.agent_card is None

    async def test_default_registration_calls_register_agent_without_card(self):
        """The default worker still registers automatically and passes no card,
        preserving existing callers and wire behavior."""
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        worker = AgentexWorker(task_queue="test-queue", health_check_port=8080)

        with patch(
            "agentex.lib.core.temporal.workers.worker.register_agent", new=AsyncMock()
        ) as mock_register, patch(
            "agentex.lib.core.temporal.workers.worker.assert_backend_compatible",
            new=AsyncMock(),
        ), patch(
            "agentex.lib.core.temporal.workers.worker.EnvironmentVariables"
        ) as mock_env_cls:
            env = self._env_vars_mock()
            mock_env_cls.refresh.return_value = env

            await worker._register_agent()

        mock_register.assert_awaited_once_with(env, agent_card=None)

    async def test_supplied_card_forwarded_exactly_once_by_run_lifecycle(self):
        """A card passed to the constructor reaches register_agent exactly once
        through the existing automatic registration in run(); no second
        registration call is introduced."""
        from agentex.lib.types.agent_card import AgentCard
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        card = AgentCard(metadata={"permits_capable": True})
        worker = AgentexWorker(
            task_queue="test-queue", health_check_port=8080, agent_card=card
        )

        with patch.object(
            worker, "start_health_check_server", new=AsyncMock()
        ), patch(
            "agentex.lib.core.temporal.workers.worker.register_agent", new=AsyncMock()
        ) as mock_register, patch(
            "agentex.lib.core.temporal.workers.worker.assert_backend_compatible",
            new=AsyncMock(),
        ), patch(
            "agentex.lib.core.temporal.workers.worker.EnvironmentVariables"
        ) as mock_env_cls, patch(
            "agentex.lib.core.temporal.workers.worker.get_temporal_client",
            new=AsyncMock(return_value=MagicMock()),
        ), patch(
            "agentex.lib.core.temporal.workers.worker.Worker"
        ) as mock_worker_cls:
            env = self._env_vars_mock()
            mock_env_cls.refresh.return_value = env
            mock_worker_cls.return_value.run = AsyncMock()

            await worker.run(activities=[], workflows=[MagicMock()])

        mock_register.assert_awaited_once_with(env, agent_card=card)

    async def test_worker_and_fastacp_paths_serialize_the_same_card_shape(self):
        """The worker path and the FastACP/BaseACPServer lifespan path hand the
        same card to register_agent, so the registration payload's
        registration_metadata.agent_card is identical."""
        from agentex.lib.types.agent_card import AgentCard
        from agentex.lib.core.temporal.workers.worker import AgentexWorker
        from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer

        card = AgentCard(metadata={"permits_capable": True, "region": "us"})

        worker_payloads = []
        worker = AgentexWorker(
            task_queue="test-queue", health_check_port=8080, agent_card=card
        )
        with patch(
            "agentex.lib.core.temporal.workers.worker.assert_backend_compatible",
            new=AsyncMock(),
        ), patch(
            "agentex.lib.core.temporal.workers.worker.EnvironmentVariables"
        ) as mock_env_cls, patch(
            "agentex.lib.utils.registration.httpx.AsyncClient",
            new=self._httpx_client_mock(worker_payloads),
        ):
            mock_env_cls.refresh.return_value = self._env_vars_mock()
            await worker._register_agent()

        acp_payloads = []
        server = BaseACPServer.create()
        server._agent_card = card
        lifespan = server.get_lifespan_function()
        with patch(
            "agentex.lib.sdk.fastacp.base.base_acp_server.assert_backend_compatible",
            new=AsyncMock(),
        ), patch(
            "agentex.lib.sdk.fastacp.base.base_acp_server.EnvironmentVariables"
        ) as mock_env_cls, patch(
            "agentex.lib.sdk.fastacp.base.base_acp_server.shutdown_default_span_queue",
            new=AsyncMock(),
        ), patch(
            "agentex.lib.utils.registration.httpx.AsyncClient",
            new=self._httpx_client_mock(acp_payloads),
        ):
            mock_env_cls.refresh.return_value = self._env_vars_mock()
            async with lifespan(MagicMock()):
                pass

        assert len(worker_payloads) == 1
        assert len(acp_payloads) == 1
        worker_card = worker_payloads[0]["registration_metadata"]["agent_card"]
        acp_card = acp_payloads[0]["registration_metadata"]["agent_card"]
        assert worker_card == acp_card == card.model_dump()


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
