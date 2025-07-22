from copy import deepcopy
from functools import reduce, singledispatch
from typing import Any

from agentex.lib.types.llm_messages import (
    Choice,
    Completion,
    Delta,
    ToolCall,
    ToolCallRequest,
)


@singledispatch
def _concat_chunks(a: None, b: Any):
    return b


@_concat_chunks.register
def _(a: Completion, b: Completion) -> Completion:
    a.choices = [_concat_chunks(*c) for c in zip(a.choices, b.choices, strict=False)]
    return a


@_concat_chunks.register
def _(a: Choice, b: Choice) -> Choice:
    if hasattr(a, "index") and hasattr(b, "index"):
        assert a.index == b.index

    if hasattr(a, "delta") and hasattr(b, "delta"):
        a.delta = _concat_chunks(a.delta, b.delta)

    a.finish_reason = a.finish_reason or b.finish_reason
    return a


@_concat_chunks.register
def _(a: Delta, b: Delta) -> Delta:
    a.content = a.content + b.content if a.content and b.content else a.content or b.content

    if hasattr(a, "tool_calls") and hasattr(b, "tool_calls") and a.tool_calls and b.tool_calls:
        # Group tool calls by index
        grouped_tool_calls = {}
        for tool_call in a.tool_calls + b.tool_calls:
            if tool_call.index not in grouped_tool_calls:
                grouped_tool_calls[tool_call.index] = tool_call
            else:
                grouped_tool_calls[tool_call.index] = _concat_chunks(
                    grouped_tool_calls[tool_call.index], tool_call
                )

        a.tool_calls = list(grouped_tool_calls.values())
    elif hasattr(b, "tool_calls") and b.tool_calls:
        a.tool_calls = b.tool_calls

    return a


@_concat_chunks.register
def _(a: ToolCallRequest, b: ToolCallRequest) -> ToolCallRequest:
    # Preserve id from either a or b, with preference for a
    id_val = a.id if a.id is not None else b.id

    # Use index from either a or b, with preference for a's index
    index_val = a.index if hasattr(a, "index") and a.index is not None else b.index

    # Concatenate the function part
    function_val = (
        _concat_chunks(a.function, b.function)
        if a.function and b.function
        else a.function or b.function
    )

    # Set all properties
    a.id = id_val
    a.index = index_val
    a.function = function_val

    return a


@_concat_chunks.register
def _(a: ToolCall, b: ToolCall) -> ToolCall:
    # Preserve name from either a or b, with preference for a
    name_val = a.name or b.name

    # Concatenate arguments string
    args_val = ""
    if a.arguments is not None and b.arguments is not None:
        args_val = a.arguments + b.arguments
    else:
        args_val = a.arguments or b.arguments

    # Set all properties
    a.name = name_val
    a.arguments = args_val

    return a


def concat_completion_chunks(chunks: list[Completion]) -> Completion:
    """
    Accumulates all chunks returned from a streaming completion call into a `Completion` message.
    This is useful when you stream responses from an LLM and want to keep track of the context (i.e. previous messages + current message).

    Args:
        chunks: list of completion chunks returned from streamed completion
    Returns:
        Completion: same as type returned from non-streaming completion



    To implement `concat_completion_chunks` we first implement a binary `_concat_chunks` function for each
    type. Using `singledispatch` to dispatch the call to the appropriate function based on the type of the first argument.
    Each nested type is then concatenated. We can then use reduce to accumulate the entire stream into a single a
    single `CompletionChunk`. Finally we convert the type to the appropriate non-streaming type `Completion` and return it.
    """
    if not chunks:
        return None

    chunks_copy = chunks.copy()
    chunks_copy[0] = deepcopy(chunks_copy[0])  # _concat_chunks mutates first argument
    accumulated_chunks = reduce(_concat_chunks, chunks_copy)

    data = accumulated_chunks.model_dump()
    data["object"] = "chat.completion"
    choices = data["choices"]
    for choice in choices:
        choice["message"] = choice.pop("delta")

    return Completion.model_validate(data)
