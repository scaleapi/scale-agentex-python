import json
from abc import ABC, abstractmethod
from typing import Any, Literal, override

from agentex.lib.types.llm_messages import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolCallRequest,
    ToolMessage,
    UserMessage,
)
from agentex.types.data_content import DataContent
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent


class TaskMessageConverter(ABC):
    """
    Abstract base class for converting a specific type of TaskMessage to an LLM Message.

    Each converter should be responsible for one content type.
    """

    @abstractmethod
    def convert(self, task_message: TaskMessage) -> Message:
        """
        Convert a TaskMessage to an LLM Message.

        Args:
            task_message: The TaskMessage to convert

        Returns:
            A Message (Pydantic model)
        """
        pass


class DefaultTextContentConverter(TaskMessageConverter):
    """Converter for TEXT content type."""

    @override
    def convert(self, task_message: TaskMessage) -> Message:
        """Convert TEXT content to UserMessage or AssistantMessage based on author."""
        if not isinstance(task_message.content, TextContent):
            raise ValueError(f"Expected TextContent, got {type(task_message.content)}")
        content = task_message.content
        if content.author == "user":
            return UserMessage(content=content.content)
        else:  # AGENT or custom author
            return AssistantMessage(content=content.content)


class DefaultToolRequestConverter(TaskMessageConverter):
    """Converter for TOOL_REQUEST content type."""

    @override
    def convert(self, task_message: TaskMessage) -> Message:
        """Convert TOOL_REQUEST content to AssistantMessage with tool_calls."""
        if not isinstance(task_message.content, ToolRequestContent):
            raise ValueError(f"Expected ToolRequestContent, got {type(task_message.content)}")
        
        content = task_message.content

        # Ensure arguments are properly JSON serialized
        arguments_str = json.dumps(content.arguments)

        tool_call = ToolCallRequest(
            id=content.tool_call_id,
            function=ToolCall(name=content.name, arguments=arguments_str),
        )
        return AssistantMessage(content=None, tool_calls=[tool_call])


class DefaultToolResponseConverter(TaskMessageConverter):
    """Converter for TOOL_RESPONSE content type."""

    @override
    def convert(self, task_message: TaskMessage) -> Message:
        """Convert TOOL_RESPONSE content to ToolMessage."""
        if not isinstance(task_message.content, ToolResponseContent):
            raise ValueError(f"Expected ToolResponseContent, got {type(task_message.content)}")
            
        content = task_message.content
        return ToolMessage(
            content=str(content.content),
            tool_call_id=content.tool_call_id,
            name=content.name,
        )


class DefaultDataContentConverter(TaskMessageConverter):
    """Converter for DATA content type."""

    @override
    def convert(self, task_message: TaskMessage) -> Message:
        """Convert DATA content to UserMessage or AssistantMessage based on author."""
        if not isinstance(task_message.content, DataContent):
            raise ValueError(f"Expected DataContent, got {type(task_message.content)}")
        
        content = task_message.content
        content_str = str(content.data)
        if content.author == "user":
            return UserMessage(content=content_str)
        else:  # AGENT or custom author
            return AssistantMessage(content=content_str)


class DefaultUnknownContentConverter(TaskMessageConverter):
    """Converter for unknown content types."""

    @override
    def convert(self, task_message: TaskMessage) -> Message:
        """Convert unknown content types to AssistantMessage with fallback text."""
        
        content = task_message.content
        fallback_content = f"Unknown message type: {content.type}"
        return AssistantMessage(content=fallback_content)


def convert_task_message_to_llm_messages(
    task_message: TaskMessage,
    output_mode: Literal["pydantic", "dict"] = "pydantic",
    text_converter: TaskMessageConverter | None = None,
    tool_request_converter: TaskMessageConverter | None = None,
    tool_response_converter: TaskMessageConverter | None = None,
    data_converter: TaskMessageConverter | None = None,
    unknown_converter: TaskMessageConverter | None = None,
) -> Message | dict[str, Any]:
    """
    Convert a TaskMessage to an LLM Message format.

    Args:
        task_message: The TaskMessage to convert
        output_mode: Whether to return a Pydantic model or dict
        text_converter: Optional converter for TEXT content. Uses DefaultTextContentConverter if None.
        tool_request_converter: Optional converter for TOOL_REQUEST content. Uses DefaultToolRequestConverter if None.
        tool_response_converter: Optional converter for TOOL_RESPONSE content. Uses DefaultToolResponseConverter if None.
        data_converter: Optional converter for DATA content. Uses DefaultDataContentConverter if None.
        unknown_converter: Optional converter for unknown content. Uses DefaultUnknownContentConverter if None.

    Returns:
        Either a Message (Pydantic model) or dict representation
    """
    content = task_message.content

    # Get the appropriate converter for this content type
    if content.type == "text":
        converter = (
            text_converter
            if text_converter is not None
            else DefaultTextContentConverter()
        )
    elif content.type == "tool_request":
        converter = (
            tool_request_converter
            if tool_request_converter is not None
            else DefaultToolRequestConverter()
        )
    elif content.type == "tool_response":
        converter = (
            tool_response_converter
            if tool_response_converter is not None
            else DefaultToolResponseConverter()
        )
    elif content.type == "data":
        converter = (
            data_converter
            if data_converter is not None
            else DefaultDataContentConverter()
        )
    else:
        converter = (
            unknown_converter
            if unknown_converter is not None
            else DefaultUnknownContentConverter()
        )

    message = converter.convert(task_message)

    if output_mode == "dict":
        return message.model_dump()
    return message


def convert_task_messages_to_llm_messages(
    task_messages: list[TaskMessage],
    output_mode: Literal["pydantic", "dict"] = "pydantic",
    text_converter: TaskMessageConverter | None = None,
    tool_request_converter: TaskMessageConverter | None = None,
    tool_response_converter: TaskMessageConverter | None = None,
    data_converter: TaskMessageConverter | None = None,
    unknown_converter: TaskMessageConverter | None = None,
) -> list[Message | dict[str, Any]]:
    """
    Convert a list of TaskMessages to LLM Message format.

    Args:
        task_messages: List of TaskMessages to convert
        output_mode: Whether to return Pydantic models or dicts
        text_converter: Optional converter for TEXT content. Uses DefaultTextContentConverter if None.
        tool_request_converter: Optional converter for TOOL_REQUEST content. Uses DefaultToolRequestConverter if None.
        tool_response_converter: Optional converter for TOOL_RESPONSE content. Uses DefaultToolResponseConverter if None.
        data_converter: Optional converter for DATA content. Uses DefaultDataContentConverter if None.
        unknown_converter: Optional converter for unknown content. Uses DefaultUnknownContentConverter if None.

    Returns:
        List of either Messages (Pydantic models) or dicts
    """
    return [
        convert_task_message_to_llm_messages(
            task_message,
            output_mode,
            text_converter,
            tool_request_converter,
            tool_response_converter,
            data_converter,
            unknown_converter,
        )
        for task_message in task_messages
    ]
