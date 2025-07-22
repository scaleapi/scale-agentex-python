from enum import Enum

from temporalio import activity

from agentex.lib.core.services.adk.providers.sgp import SGPService
from agentex.lib.types.files import FileContentResponse
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class SGPActivityName(str, Enum):
    DOWNLOAD_FILE_CONTENT = "download-file-content"


class DownloadFileParams(BaseModelWithTraceParams):
    file_id: str
    filename: str


class SGPActivities:
    def __init__(self, sgp_service: SGPService):
        self.sgp_service = sgp_service

    @activity.defn(name=SGPActivityName.DOWNLOAD_FILE_CONTENT)
    async def download_file_content(self, params: DownloadFileParams) -> FileContentResponse:
        """
        Download file content from SGP.

        Args:
            params: DownloadFileParams containing file_id and filename.

        Returns:
            FileContentResponse with mime_type and base64_content for constructing LLM input.
        """
        return await self.sgp_service.download_file_content(
            file_id=params.file_id,
            filename=params.filename,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
