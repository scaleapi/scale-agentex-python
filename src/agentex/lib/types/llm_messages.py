from typing import Any, Literal

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated
from pydantic import Field

from agentex.lib.utils.model_utils import BaseModel


class LLMConfig(BaseModel):
    """
    LLMConfig is the configuration for the LLM.

    Attributes:
        model: The model to use
        messages: The messages to send to the LLM
        temperature: The temperature to use
        top_p: The top_p to use
        n: The number of completions to generate
        stream: Whether to stream the completions
        stream_options: The options for the stream
        stop: The stop sequence to use
        max_tokens: The maximum number of tokens to generate
        max_completion_tokens: The maximum number of tokens to generate for the completion
        presence_penalty: The presence penalty to use
        frequency_penalty: The frequency penalty to use
        logit_bias: The logit bias to use
        response_format: The response format to use
        seed: The seed to use
        tools: The tools to use
        tool_choice: The tool choice to use
        parallel_tool_calls: Whether to allow parallel tool calls
        logprobs: Whether to return log probabilities
        top_logprobs: The number of top log probabilities to return
    """

    model: str
    messages: list = []
    temperature: float | None = None
    top_p: float | None = None
    n: int | None = None
    stream: bool | None = None
    stream_options: dict | None = None
    stop: str | list | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    logit_bias: dict | None = None
    response_format: dict | type[BaseModel] | str | None = None
    seed: int | None = None
    tools: list | None = None
    tool_choice: str | None = None
    parallel_tool_calls: bool | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None


class ContentPartText(BaseModel):
    """
    ContentPartText is the text content of the message.

    Attributes:
        text: The text content.
        type: The type of the content part.
    """

    text: str = Field(..., description="The text content.")
    type: Literal["text"] = Field(
        default="text", description="The type of the content part."
    )


class ImageURL(BaseModel):
    """
    ImageURL is the URL of the image.

    Attributes:
        url: The URL of the image.
        detail: The detail level of the image.
    """

    url: str = Field(
        ..., description="Either a URL of the image or the base64 encoded image data."
    )
    detail: Literal["auto", "low", "high"] = Field(
        ...,
        description="""Specifies the detail level of the image.

Learn more in the
[Vision guide](https://platform.openai.com/docs/guides/vision/low-or-high-fidelity-image-understanding).
""",
    )


class ContentPartImage(BaseModel):
    """
    ContentPartImage is the image content of the message.

    Attributes:
        image_url: The URL of the image.
        type: The type of the content part.
    """

    image_url: ImageURL = Field(..., description="The image URL.")
    type: Literal["image_url"] = Field(..., description="The type of the content part.")


class FileContent(BaseModel):
    """
    FileContent is the file content of the message.

    Attributes:
        filename: The name of the file.
        file_data: The base64 encoded file data with MIME type, e.g., 'data:application/pdf;base64,...'
    """

    filename: str = Field(..., description="The name of the file.")
    file_data: str = Field(
        ...,
        description="The base64 encoded file data with MIME type, e.g., 'data:application/pdf;base64,...'",
    )


class ContentPartFile(BaseModel):
    """
    ContentPartFile is the file content of the message.

    Attributes:
        file: The file content.
        type: The type of the content part.
    """

    file: FileContent = Field(..., description="The file content.")
    type: Literal["file"] = Field(
        default="file", description="The type of the content part."
    )


ContentPart = ContentPartText | ContentPartImage | ContentPartFile


class SystemMessage(BaseModel):
    """
    SystemMessage is the system message of the message.

    Attributes:
        role: The role of the messages author, in this case `system`.
        content: The contents of the system message.
    """

    role: Literal["system"] = Field(
        default="system",
        description="The role of the messages author, in this case `system`.",
    )
    content: str = Field(..., description="The contents of the system message.")


class UserMessage(BaseModel):
    """
    UserMessage is the user message of the message.

    Attributes:
        role: The role of the messages author, in this case `user`.
        content: The contents of the user message.
    """

    role: Literal["user"] = Field(
        default="user",
        description="The role of the messages author, in this case `user`.",
    )
    content: str | list[ContentPart] = Field(
        ...,
        description="The contents of the user message. Can be a string or a list of content parts.",
    )


class ToolCall(BaseModel):
    """
    ToolCall is the tool call of the message.

    Attributes:
        name: The name of the function to call.
        arguments: The arguments to call the function with, as generated by the model in JSON format.
    """

    name: str | None = Field(
        default=None, description="The name of the function to call."
    )
    arguments: str | None = Field(
        default=None,
        description="""
The arguments to call the function with, as generated by the model in JSON
format. Note that the model does not always generate valid JSON, and may
hallucinate parameters not defined by your function schema. Validate the
arguments in your code before calling your function.
""",
    )


class ToolCallRequest(BaseModel):
    """
    ToolCallRequest is the tool call request of the message.

    Attributes:
        type: The type of the tool. Currently, only `function` is supported.
        id: The ID of the tool call request.
        function: The function that the model is requesting.
        index: The index of the tool call request.
    """

    type: Literal["function"] = Field(
        default="function",
        description="The type of the tool. Currently, only `function` is supported.",
    )
    id: str | None = Field(default=None, description="The ID of the tool call request.")
    function: ToolCall = Field(
        ..., description="The function that the model is requesting."
    )
    index: int | None = None


class AssistantMessage(BaseModel):
    """
    AssistantMessage is the assistant message of the message.

    Attributes:
        role: The role of the messages author, in this case `assistant`.
        content: The contents of the assistant message.
        tool_calls: The tool calls generated by the model, such as function calls.
        parsed: The parsed content of the message to a specific type
    """

    role: Literal["assistant"] = Field(
        default="assistant",
        description="The role of the messages author, in this case `assistant`.",
    )
    content: str | None = Field(
        default=None,
        description="""The contents of the assistant message.

Required unless `tool_calls` or `function_call` is specified.
""",
    )
    tool_calls: list[ToolCallRequest] | None = Field(
        default=None,
        description="The tool calls generated by the model, such as function calls.",
    )
    parsed: Any | None = Field(
        default=None, description="The parsed content of the message to a specific type"
    )


class ToolMessage(BaseModel):
    """
    ToolMessage is the tool message of the message.

    Attributes:
        role: The role of the messages author, in this case `tool`.
        content: The contents of the tool message.
        tool_call_id: The tool call that this message is responding to.
        name: The name of the tool called.
        is_error: Whether the tool call was successful.
    """

    role: Literal["tool"] = Field(
        default="tool",
        description="The role of the messages author, in this case `tool`.",
    )
    content: str | list[ContentPart] = Field(
        ..., description="The contents of the tool message."
    )
    tool_call_id: str = Field(
        ..., description="Tool call that this message is responding to."
    )
    # name is optional based on OAI API defined here for chat_completion_input: https://platform.openai.com/docs/api-reference/chat/create
    name: str | None = Field(default=None, description="The name of the tool called.")
    is_error: bool | None = Field(
        default=None, description="Whether the tool call was successful."
    )


Message = Annotated[
    SystemMessage | UserMessage | AssistantMessage | ToolMessage,
    Field(discriminator="role"),
]


class Delta(BaseModel):
    """
    Delta is the delta of the message.

    Attributes:
        content: The content of the delta.
        role: The role of the delta.
        tool_calls: The tool calls of the delta.
    """

    content: str | None = Field(default=None)
    role: str | None = Field(default=None)
    tool_calls: list[ToolCallRequest] | None = Field(default=None)


class Choice(BaseModel):
    """
    Choice is the choice of the message.

    Attributes:
        index: The index of the choice.
        finish_reason: The finish reason of the choice.
        message: The message of the choice.
        delta: The delta of the choice.
    """

    index: int
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls"] | None = (
        None
    )
    message: AssistantMessage | None = None
    delta: Delta | None = None


class Usage(BaseModel):
    """
    Usage is the usage of the message.

    Attributes:
        prompt_tokens: The number of prompt tokens.
        completion_tokens: The number of completion tokens.
        total_tokens: The total number of tokens.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Completion(BaseModel):
    """
    Completion is the completion of the message.

    Attributes:
        choices: The choices of the completion.
        created: The created time of the completion.
        model: The model of the completion.
        usage: The usage of the completion.
    """

    choices: list[Choice]
    created: int | None = None
    model: str | None = None
    usage: Usage | None = None
