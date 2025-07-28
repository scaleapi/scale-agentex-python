import dataclasses
import datetime
import os
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from aiohttp import web
from temporalio.client import Client
from temporalio.converter import (
    AdvancedJSONEncoder,
    CompositePayloadConverter,
    DataConverter,
    DefaultPayloadConverter,
    JSONPlainPayloadConverter,
    JSONTypeConverter,
    _JSONTypeConverterUnhandled,
)
from temporalio.runtime import OpenTelemetryConfig, Runtime, TelemetryConfig
from temporalio.worker import (
    UnsandboxedWorkflowRunner,
    Worker,
)

from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.registration import register_agent
from agentex.lib.environment_variables import EnvironmentVariables

logger = make_logger(__name__)


class DateTimeJSONEncoder(AdvancedJSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)


class DateTimeJSONTypeConverter(JSONTypeConverter):
    def to_typed_value(
        self, hint: type, value: Any
    ) -> Any | None | _JSONTypeConverterUnhandled:
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


async def get_temporal_client(temporal_address: str, metrics_url: str = None) -> Client:
    if not metrics_url:
        client = await Client.connect(
            target_host=temporal_address, data_converter=custom_data_converter
        )
    else:
        runtime = Runtime(
            telemetry=TelemetryConfig(metrics=OpenTelemetryConfig(url=metrics_url))
        )
        client = await Client.connect(
            target_host=temporal_address,
            data_converter=custom_data_converter,
            runtime=runtime,
        )
    return client


class AgentexWorker:
    def __init__(
        self,
        task_queue,
        max_workers: int = 10,
        max_concurrent_activities: int = 10,
        health_check_port: int = 80,
    ):
        self.task_queue = task_queue
        self.activity_handles = []
        self.max_workers = max_workers
        self.max_concurrent_activities = max_concurrent_activities
        self.health_check_server_running = False
        self.healthy = False
        self.health_check_port = health_check_port

    async def run(
        self,
        activities: list[Callable],
        workflow: type,
    ):
        await self.start_health_check_server()
        await self._register_agent()
        temporal_client = await get_temporal_client(
            temporal_address=os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        )
        
        # Enable debug mode if AgentEx debug is enabled (disables deadlock detection)
        debug_enabled = os.environ.get("AGENTEX_DEBUG_ENABLED", "false").lower() == "true"
        if debug_enabled:
            logger.info("🐛 [WORKER] Temporal debug mode enabled - deadlock detection disabled")
        
        worker = Worker(
            client=temporal_client,
            task_queue=self.task_queue,
            activity_executor=ThreadPoolExecutor(max_workers=self.max_workers),
            workflows=[workflow],
            activities=activities,
            workflow_runner=UnsandboxedWorkflowRunner(),
            max_concurrent_activities=self.max_concurrent_activities,
            build_id=str(uuid.uuid4()),
            debug_mode=debug_enabled,  # Disable deadlock detection in debug mode
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
            app.router.add_get("/readyz", lambda request: self._health_check())

            # Disable access logging
            runner = web.AppRunner(app, access_log=None)
            await runner.setup()

            try:
                site = web.TCPSite(runner, "0.0.0.0", self.health_check_port)
                await site.start()
                logger.info(
                    f"Health check server running on http://0.0.0.0:{self.health_check_port}/readyz"
                )
                self.health_check_server_running = True
            except OSError as e:
                logger.error(
                    f"Failed to start health check server on port {self.health_check_port}: {e}"
                )
                # Try alternative port if default fails
                try:
                    alt_port = self.health_check_port + 1
                    site = web.TCPSite(runner, "0.0.0.0", alt_port)
                    await site.start()
                    logger.info(
                        f"Health check server running on alternative port http://0.0.0.0:{alt_port}/readyz"
                    )
                    self.health_check_server_running = True
                except OSError as e:
                    logger.error(
                        f"Failed to start health check server on alternative port {alt_port}: {e}"
                    )
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