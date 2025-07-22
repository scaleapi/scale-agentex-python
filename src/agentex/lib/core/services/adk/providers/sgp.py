import base64
import os
import tempfile

from scale_gp import SGPClient

from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.types.files import FileContentResponse
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import heartbeat_if_in_workflow

logger = make_logger(__name__)


class SGPService:
    def __init__(self, sgp_client: SGPClient, tracer: AsyncTracer):
        self.sgp_client = sgp_client
        self.tracer = tracer

    async def download_file_content(
        self,
        file_id: str,
        filename: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> FileContentResponse:
        """
        Download file content from SGP.

        Args:
            file_id: The ID of the file to download.
            filename: The filename of the file to download.
            trace_id: The trace ID for tracing.
            parent_span_id: The parent span ID for tracing.

        Returns:
            FileContentResponse with mime_type and base64_content for constructing LLM input.
        """
        trace = self.tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="download_file_content",
            input={"file_id": file_id, "filename": filename},
        ) as span:
            logger.info(f"Downloading file content for file_id: {file_id}")
            heartbeat_if_in_workflow("downloading file content")

            # Get the SGP response
            response = self.sgp_client.beta.files.content(file_id)
            heartbeat_if_in_workflow("file content downloaded")

            # Determine mime type based on file extension
            mime_type = "application/pdf"  # Default
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension:
                if file_extension == ".pdf":
                    mime_type = "application/pdf"
                elif file_extension in [".doc", ".docx"]:
                    mime_type = "application/msword"
                elif file_extension in [".txt", ".text"]:
                    mime_type = "text/plain"
                elif file_extension in [".png"]:
                    mime_type = "image/png"
                elif file_extension in [".jpg", ".jpeg"]:
                    mime_type = "image/jpeg"

            # Use a named temporary file - simpler approach
            with tempfile.NamedTemporaryFile(suffix=file_extension) as temp_file:
                heartbeat_if_in_workflow(f"saving to temp file: {temp_file.name}")

                # Use write_to_file method if available
                if hasattr(response, "write_to_file"):
                    response.write_to_file(temp_file.name)
                else:
                    # Fallback to direct writing
                    content_bytes = response.read()
                    temp_file.write(content_bytes)
                    temp_file.flush()

                # Seek to beginning of file for reading
                temp_file.seek(0)

                # Read the file in binary mode - exactly like the example
                data = temp_file.read()

                # Encode to base64
                base64_content = base64.b64encode(data).decode("utf-8")

                result = FileContentResponse(
                    mime_type=mime_type, base64_content=base64_content
                )

            # Record metadata for tracing
            span.output = {
                "file_id": file_id,
                "mime_type": result.mime_type,
                "content_size": len(result.base64_content),
            }
            return result
