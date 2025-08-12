from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable

from fastapi import FastAPI

from agentex.lib.core.clients.temporal.temporal_client import TemporalClient
from agentex.lib.core.temporal.services.temporal_task_service import TemporalTaskService
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.types.acp import (
    CancelTaskParams,
    CreateTaskParams,
    SendEventParams,
)
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class TemporalACP(BaseACPServer):
    """
    Temporal-specific implementation of AsyncAgentACP.
    Uses TaskService to forward operations to temporal workflows.
    """

    def __init__(
        self, temporal_address: str, temporal_task_service: TemporalTaskService | None = None
    ):
        super().__init__()
        self._temporal_task_service = temporal_task_service
        self._temporal_address = temporal_address

    @classmethod
    def create(cls, temporal_address: str) -> "TemporalACP":
        logger.info("Initializing TemporalACP instance")

        # Create instance without temporal client initially
        temporal_acp = cls(temporal_address=temporal_address)
        temporal_acp._setup_handlers()
        logger.info("TemporalACP instance initialized now")
        return temporal_acp

    # This is to override the lifespan function of the base
    def get_lifespan_function(self) -> Callable[[FastAPI], AsyncGenerator[None, None]]:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Create temporal client during startup
            if self._temporal_address is None:
                raise ValueError("Temporal address is not set")

            if self._temporal_task_service is None:
                env_vars = EnvironmentVariables.refresh()
                temporal_client = await TemporalClient.create(
                    temporal_address=self._temporal_address
                )
                self._temporal_task_service = TemporalTaskService(
                    temporal_client=temporal_client,
                    env_vars=env_vars,
                )

            # Call parent lifespan for agent registration
            async with super().get_lifespan_function()(app):
                yield

        return lifespan

    def _setup_handlers(self):
        """Set up the handlers for temporal workflow operations"""

        @self.on_task_create
        async def handle_task_create(params: CreateTaskParams) -> None:
            """Default create task handler - logs the task"""
            logger.info(f"TemporalACP received task create rpc call for task {params.task.id}")
            await self._temporal_task_service.submit_task(agent=params.agent, task=params.task, params=params.params)

        @self.on_task_event_send
        async def handle_event_send(params: SendEventParams) -> None:
            """Forward messages to running workflows via TaskService"""
            try:
                await self._temporal_task_service.send_event(
                    agent=params.agent,
                    task=params.task,
                    event=params.event,
                )

            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                raise

        @self.on_task_cancel
        async def handle_cancel(params: CancelTaskParams) -> None:
            """Cancel running workflows via TaskService"""
            try:
                await self._temporal_task_service.cancel(task_id=params.task.id)
            except Exception as e:
                logger.error(f"Failed to cancel task: {e}")
                raise
