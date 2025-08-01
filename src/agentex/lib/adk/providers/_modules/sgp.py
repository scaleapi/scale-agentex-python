from datetime import timedelta

from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from scale_gp import SGPClient, SGPClientError
from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.core.services.adk.providers.sgp import SGPService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.providers.sgp_activities import (
    DownloadFileParams,
    FileContentResponse,
    SGPActivityName,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class SGPModule:
    """
    Module for managing SGP agent operations in Agentex.
    Provides high-level methods for chat completion, streaming, agentic streaming, and message classification.
    """

    def __init__(
        self,
        sgp_service: SGPService | None = None,
    ):
        if sgp_service is None:
            try:
                sgp_client = SGPClient()
                agentex_client = create_async_agentex_client()
                tracer = AsyncTracer(agentex_client)
                self._sgp_service = SGPService(sgp_client=sgp_client, tracer=tracer)
            except SGPClientError:
                self._sgp_service = None
        else:
            self._sgp_service = sgp_service

    async def download_file_content(
        self,
        params: DownloadFileParams,
        start_to_close_timeout: timedelta = timedelta(seconds=30),
        heartbeat_timeout: timedelta = timedelta(seconds=30),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> FileContentResponse:
        """
        Download the content of a file from SGP.

        Args:
            params (DownloadFileParams): The parameters for the download file content activity.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            FileContentResponse: The content of the file
        """
        if self._sgp_service is None:
            raise ValueError(
                "SGP activities are disabled because the SGP client could not be initialized. Please check that the SGP_API_KEY environment variable is set."
            )

        params = DownloadFileParams(
            file_id=params.file_id,
            filename=params.filename,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=SGPActivityName.DOWNLOAD_FILE_CONTENT,
                request=params,
                response_type=FileContentResponse,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._sgp_service.download_file_content(
                file_id=params.file_id,
                filename=params.filename,
            )
