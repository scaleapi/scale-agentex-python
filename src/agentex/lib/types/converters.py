from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
import json
from agents import TResponseInputItem


def convert_task_messages_to_oai_agents_inputs(
    task_messages: list[TaskMessage],
) -> list[TResponseInputItem]:
    """
    Convert a list of TaskMessages to a list of OpenAI Agents SDK inputs (TResponseInputItem).

    Args:
        task_messages: The list of TaskMessages to convert.

    Returns:
        A list of OpenAI Agents SDK inputs (TResponseInputItem).
    """
    converted_messages = []
    for task_message in task_messages:
        task_message_content = task_message.content
        if isinstance(task_message_content, TextContent):
            converted_messages.append(
                {
                    "role": (
                        "user" if task_message_content.author == "user" else "assistant"
                    ),
                    "content": task_message_content.content,
                }
            )
        elif isinstance(task_message_content, ToolRequestContent):
            converted_messages.append(
                {
                    "type": "function_call",
                    "call_id": task_message_content.tool_call_id,
                    "name": task_message_content.name,
                    "arguments": json.dumps(task_message_content.arguments),
                }
            )
        elif isinstance(task_message_content, ToolResponseContent):
            content_str = (
                task_message_content.content
                if isinstance(task_message_content.content, str)
                else json.dumps(task_message_content.content)
            )
            converted_messages.append(
                {
                    "type": "function_call_output",
                    "call_id": task_message_content.tool_call_id,
                    "output": content_str,
                }
            )
        else:
            raise ValueError(
                f"Unsupported content type for converting TaskMessage to OpenAI Agents SDK input: {type(task_message.content)}"
            )

    return converted_messages
