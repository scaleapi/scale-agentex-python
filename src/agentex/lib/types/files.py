from agentex.lib.utils.model_utils import BaseModel


class FileContentResponse(BaseModel):
    """Response model for downloaded file content.

    Attributes:
        mime_type: The MIME type of the file
        base64_content: The base64 encoded content of the file
    """

    mime_type: str
    base64_content: str
