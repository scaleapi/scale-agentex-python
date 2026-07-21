from __future__ import annotations

import os
import uuid
import datetime
import dataclasses
from typing import Any, overload, override
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from aiohttp import web
from temporalio.client import Client, Plugin as ClientPlugin
from temporalio.worker import (
    Plugin as WorkerPlugin,
    Worker,
    Interceptor,
    UnsandboxedWorkflowRunner,
)
from temporalio.runtime import Runtime, TelemetryConfig, OpenTelemetryConfig
from temporalio.converter import (
    PayloadCodec,
    DataConverter,
    JSONTypeConverter,
    AdvancedJSONEncoder,
    DefaultPayloadConverter,
    CompositePayloadConverter,
    JSONPlainPayloadConverter,
)

from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.registration import register_agent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.compat.version_guard import assert_backend_compatible

logger = make_logger(__name__)


class DateTimeJSONEncoder(AdvancedJSONEncoder):
    @override
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)


class DateTimeJSONTypeConverter(JSONTypeConverter):
    @override
    def to_typed_value(self, hint: type, value: Any) -> Any | None:
        if hint == datetime.datetime:
            return datetime.datetime.fromisoformat(value)
        return JSONTypeConverter.Unhandled


class DateTimePayloadConverter(CompositePayloadConverter):
    def __init__(self) -> None:
        json_converter = JSONPlainPayloadConverter(
            encoder=DateTimeJSONEncoder,
            custom_type_converters=[DateTimeJSONTypeConverter()],
        )
        super().__init__(
            *[
                c if not isinstance(c, JSONPlainPayloadConverter) else json_converter
                for c in DefaultPayloadConverter.default_encoding_payload_converters
            ]
        )


custom_data_converter = dataclasses.replace(
    DataConverter.default,
    payload_converter_class=DateTimePayloadConverter,
)


def _validate_plugins(plugins: list) -> None:
    """Validate that all items in the plugins list are valid Temporal plugins."""
    for i, plugin in enumerate(plugins):
        if not isinstance(plugin, (ClientPlugin, WorkerPlugin)):
            raise TypeError(
                f"Plugin at index {i} must be an instance of temporalio.client.Plugin "
                f"or temporalio.worker.Plugin, got {type(plugin).__name__}"
            )


def _validate_interceptors(interceptors: list) -> None:
    """Validate that all items in the interceptors list are valid Temporal interceptors."""
    for i, interceptor in enumerate(interceptors):
        if not isinstance(interceptor, Interceptor):
            raise TypeError(
                f"Interceptor at index {i} must be an instance of temporalio.worker.Interceptor, "
                f"got {type(interceptor).__name__}"
            )


def _build_otel_interceptors() -> list:
    """Return an OpenTelemetry Temporal interceptor when an OTel observability
    mode is active (SGP_OBS_MODE in {dual, lgtm}), so trace context propagates
    across the workflow -> activity boundary. This lets business spans created
    inside the model-loop activity adopt the caller's observability trace_id.

    Empty in the default dd_only mode, or when the temporalio OTel contrib is
    unavailable (safe no-op).
    """
    if os.getenv("SGP_OBS_MODE", "").strip().lower() not in ("dual", "lgtm"):
        return []
    try:
        from temporalio.contrib.opentelemetry import TracingInterceptor
    except ImportError:
        return []
    return [TracingInterceptor()]


async def get_temporal_client(
    temporal_address: str,
    metrics_url: str | None = None,
    plugins: list = [],
    payload_codec: PayloadCodec | None = None,
    data_converter: DataConverter | None = None,
) -> Client:
    if plugins != []:  # We don't need to validate the plugins if they are empty
        _validate_plugins(plugins)

    if payload_codec is not None and data_converter is not None:
        raise ValueError(
            "Pass payload_codec inside `data_converter` "
            "(DataConverter(..., payload_codec=...)) instead of as a separate "
            "kwarg. Specifying both is ambiguous."
        )

    # Lazy import to avoid pulling in opentelemetry.sdk for non-Temporal agents
    from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

    has_openai_plugin = any(isinstance(p, OpenAIAgentsPlugin) for p in (plugins or []))

    if has_openai_plugin and payload_codec is not None and data_converter is None:
        raise ValueError(
            "payload_codec passed as a kwarg alongside OpenAIAgentsPlugin would "
            "be silently dropped by the plugin's data-converter transformer. "
            "Build a DataConverter explicitly with "
            "`payload_converter_class=OpenAIPayloadConverter` (or a subclass) "
            "and `payload_codec=...`, then pass it via the `data_converter` "
            "kwarg instead."
        )

    connect_kwargs: dict[str, Any] = {
        "target_host": temporal_address,
        "plugins": plugins,
    }

    if data_converter is not None:
        connect_kwargs["data_converter"] = data_converter
    elif not has_openai_plugin:
        dc = custom_data_converter
        if payload_codec:
            dc = dataclasses.replace(dc, payload_codec=payload_codec)
        connect_kwargs["data_converter"] = dc

    otel_interceptors = _build_otel_interceptors()
    if otel_interceptors:
        connect_kwargs["interceptors"] = otel_interceptors

    if not metrics_url:
        client = await Client.connect(**connect_kwargs)
    else:
        runtime = Runtime(telemetry=TelemetryConfig(metrics=OpenTelemetryConfig(url=metrics_url)))
        connect_kwargs["runtime"] = runtime
        client = await Client.connect(**connect_kwargs)
    return client


class AgentexWorker:
    def __init__(
        self,
        task_queue,
        max_workers: int = 10,
        max_concurrent_activities: int = 10,
        health_check_port: int | None = None,
        plugins: list = [],
        interceptors: list = [],
        metrics_url: str | None = None,
        payload_codec: PayloadCodec | None = None,
        data_converter: DataConverter | None = None,
    ):
        self.task_queue = task_queue
        self.activity_handles = []
        self.max_workers = max_workers
        self.max_concurrent_activities = max_concurrent_activities
        self.health_check_server_running = False
        self.healthy = False
        self.health_check_port = (
            health_check_port if health_check_port is not None else EnvironmentVariables.refresh().HEALTH_CHECK_PORT
        )
        self.plugins = plugins
        self.interceptors = interceptors
        self.metrics_url = metrics_url
        self.payload_codec = payload_codec
        self.data_converter = data_converter

    @overload
    async def run(
        self,
        activities: list[Callable],
        *,
        workflow: type,
    ) -> None: ...

    @overload
    async def run(
        self,
        activities: list[Callable],
        *,
        workflows: list[type],
    ) -> None: ...

    async def run(
        self,
        activities: list[Callable],
        *,
        workflow: type | None = None,
        workflows: list[type] | None = None,
    ):
        await self.start_health_check_server()
        await self._register_agent()

        # Validate interceptors if any are provided
        if self.interceptors:
            _validate_interceptors(self.interceptors)

        temporal_client = await get_temporal_client(
            temporal_address=os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
            plugins=self.plugins,
            metrics_url=self.metrics_url,
            payload_codec=self.payload_codec,
            data_converter=self.data_converter,
        )

        # Enable debug mode if AgentEx debug is enabled (disables deadlock detection)
        debug_enabled = os.environ.get("AGENTEX_DEBUG_ENABLED", "false").lower() == "true"
        if debug_enabled:
            logger.info("🐛 [WORKER] Temporal debug mode enabled - deadlock detection disabled")

        if workflow is None and workflows is None:
            raise ValueError("Either workflow or workflows must be provided")

        worker = Worker(
            client=temporal_client,
            task_queue=self.task_queue,
            activity_executor=ThreadPoolExecutor(max_workers=self.max_workers),
            workflows=[workflow] if workflows is None else workflows,
            activities=activities,
            workflow_runner=UnsandboxedWorkflowRunner(),
            max_concurrent_activities=self.max_concurrent_activities,
            build_id=str(uuid.uuid4()),
            debug_mode=debug_enabled,  # Disable deadlock detection in debug mode
            interceptors=self.interceptors,  # Pass interceptors to Worker
        )

        logger.info(f"Starting workers for task queue: {self.task_queue}")
        # Eagerly set the worker status to healthy
        self.healthy = True
        logger.info(f"Running workers for task queue: {self.task_queue}")
        await worker.run()

    async def _health_check(self):
        return web.json_response(self.healthy)

    async def start_health_check_server(self):
        if not self.health_check_server_running:
            app = web.Application()
            app.router.add_get("/readyz", lambda request: self._health_check())  # noqa: ARG005

            # Disable access logging
            runner = web.AppRunner(app, access_log=None)
            await runner.setup()

            try:
                site = web.TCPSite(runner, "0.0.0.0", self.health_check_port)
                await site.start()
                logger.info(f"Health check server running on http://0.0.0.0:{self.health_check_port}/readyz")
                self.health_check_server_running = True
            except OSError as e:
                logger.error(f"Failed to start health check server on port {self.health_check_port}: {e}")
                # Try alternative port if default fails
                try:
                    alt_port = self.health_check_port + 1
                    site = web.TCPSite(runner, "0.0.0.0", alt_port)
                    await site.start()
                    logger.info(f"Health check server running on alternative port http://0.0.0.0:{alt_port}/readyz")
                    self.health_check_server_running = True
                except OSError as e:
                    logger.error(f"Failed to start health check server on alternative port {alt_port}: {e}")
                    raise

    """
    Register the worker with the Agentex server.
    
    Even though the Temporal server will also register the agent with the server,
    doing this on the worker side is required to make sure that both share the API key
    which is returned on registration and used to authenticate the worker with the Agentex server.
    """

    async def _register_agent(self):
        env_vars = EnvironmentVariables.refresh()
        if env_vars and env_vars.AGENTEX_BASE_URL:
            # Fail fast if this worker is pointed at a backend older than the SDK supports —
            # the worker process never goes through the ACP server lifespan, so it needs its
            # own guard (mirrors base_acp_server.lifespan_context).
            await assert_backend_compatible(env_vars.AGENTEX_BASE_URL)
            await register_agent(env_vars)
        else:
            logger.warning("AGENTEX_BASE_URL not set, skipping worker registration")
