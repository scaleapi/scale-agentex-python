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
    DataConverter,
    JSONTypeConverter,
    AdvancedJSONEncoder,
    DefaultPayloadConverter,
    CompositePayloadConverter,
    JSONPlainPayloadConverter,
    _JSONTypeConverterUnhandled,
)
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.registration import register_agent
from agentex.lib.environment_variables import EnvironmentVariables

logger = make_logger(__name__)


class DateTimeJSONEncoder(AdvancedJSONEncoder):
    @override
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)


class DateTimeJSONTypeConverter(JSONTypeConverter):
    @override
    def to_typed_value(self, hint: type, value: Any) -> Any | None | _JSONTypeConverterUnhandled:
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


async def get_temporal_client(temporal_address: str, metrics_url: str | None = None, plugins: list = []) -> Client:
    if plugins != []:  # We don't need to validate the plugins if they are empty
        _validate_plugins(plugins)

    # Check if OpenAI plugin is present - it needs to configure its own data converter
    has_openai_plugin = any(
        isinstance(p, OpenAIAgentsPlugin) for p in (plugins or [])
    )

    # Build connection kwargs
    connect_kwargs = {
        "target_host": temporal_address,
        "plugins": plugins,
    }

    # Only set data_converter if OpenAI plugin is not present
    if not has_openai_plugin:
        connect_kwargs["data_converter"] = custom_data_converter

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
    ):
        self.task_queue = task_queue
        self.activity_handles = []
        self.max_workers = max_workers
        self.max_concurrent_activities = max_concurrent_activities
        self.health_check_server_running = False
        self.healthy = False
        self.health_check_port = health_check_port if health_check_port is not None else EnvironmentVariables.refresh().HEALTH_CHECK_PORT
        self.plugins = plugins
        self.interceptors = interceptors

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
            await register_agent(env_vars)
        else:
            logger.warning("AGENTEX_BASE_URL not set, skipping worker registration")
