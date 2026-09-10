"""Gemini CLI stream-json parser tap for the unified harness surface.

Converts the newline-delimited JSON events emitted by
``gemini -p <prompt> --output-format stream-json`` into the canonical
``StreamTaskMessage*`` stream consumed by the Agentex harness.

Event → canonical mapping
-------------------------
init
    Fires ``on_init`` with the raw event (``session_id``, ``model``). Nothing
    is emitted: session metadata is a provider concern.

message (role=user)
    Ignored. The CLI echoes the prompt back as the first message.

message (role=assistant)
    The CLI streams the answer as ``delta: true`` chunks. The first chunk
    opens a text slot (Start(TextContent)); every chunk is a Delta(TextDelta).
    The slot is closed (Done) when a ``tool_use``, ``tool_result`` or
    ``result`` event arrives, or when the stream ends. A non-delta assistant
    message whose content matches the open slot closes it; otherwise it is
    delivered as Start + Delta + Done.

tool_use
    Start(ToolRequestContent) + Done. ``tool_id`` → ``tool_call_id``,
    ``tool_name`` → ``name``, ``parameters`` → ``arguments``.

tool_result
    Full(ToolResponseContent) keyed by ``tool_id``. ``output`` (or the error
    message when ``status == "error"``) becomes ``content["result"]``;
    ``is_error`` is set for error results.

error
    Logged (``severity`` + ``message``). Nothing is emitted.

result
    Closes any open text slot, then fires ``on_result`` with the raw event so
    the caller can read ``stats`` (tokens, duration, tool calls).

Reference: ``packages/core/src/output/types.ts`` in google-gemini/gemini-cli.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Awaitable, AsyncIterator

from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

logger = make_logger(__name__)

_MAX_RESULT_LENGTH = 4000


def _truncate(text: str) -> str:
    return str(text)[:_MAX_RESULT_LENGTH]


async def convert_gemini_cli_to_agentex_events(
    lines: AsyncIterator[str | dict[str, Any]],
    on_result: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    on_init: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> AsyncIterator[StreamTaskMessageStart | StreamTaskMessageDelta | StreamTaskMessageFull | StreamTaskMessageDone]:
    """Public tap: convert a Gemini CLI ``stream-json`` line stream to events.

    Thin wrapper over :func:`_convert_gemini_cli_impl` that owns the
    cancellation backstop: a ``finally`` closes the underlying ``lines``
    iterator (when it exposes ``aclose``) whenever this generator is closed,
    including on the ``GeneratorExit``/``CancelledError`` raised when the
    consuming task is cancelled mid-turn, so the CLI stdout handle and
    subprocess are not leaked.
    """
    inner = _convert_gemini_cli_impl(lines, on_result=on_result, on_init=on_init)
    try:
        async for event in inner:
            yield event
    finally:
        inner_aclose = getattr(inner, "aclose", None)
        if inner_aclose is not None:
            await inner_aclose()
        aclose = getattr(lines, "aclose", None)
        if aclose is not None:
            await aclose()


async def _convert_gemini_cli_impl(
    lines: AsyncIterator[str | dict[str, Any]],
    on_result: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    on_init: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> AsyncIterator[StreamTaskMessageStart | StreamTaskMessageDelta | StreamTaskMessageFull | StreamTaskMessageDone]:
    """Convert a Gemini CLI ``stream-json`` line stream into ``StreamTaskMessage*`` events.

    Each item in ``lines`` is either a raw JSON string (as read from the CLI's
    stdout) or an already-parsed dict. Empty strings are skipped; unparseable
    JSON is logged and skipped. The event → canonical mapping is documented in
    this module's docstring.
    """
    next_index = 0
    tool_call_count = 0

    # One open assistant text slot at a time: the CLI streams the answer as
    # ``delta: true`` message chunks with no explicit start/stop markers.
    text_open = False
    text_index: int | None = None
    text_buf = ""

    def _close_text() -> StreamTaskMessageDone | None:
        nonlocal text_open, text_index, text_buf
        if not text_open or text_index is None:
            return None
        done = StreamTaskMessageDone(type="done", index=text_index)
        text_open = False
        text_index = None
        text_buf = ""
        return done

    async for raw in lines:
        if not raw:
            continue

        if isinstance(raw, dict):
            evt = raw
        else:
            line = raw.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("gemini-cli: skipping non-JSON line: %r", line[:120])
                continue

        if not isinstance(evt, dict):
            continue
        evt_type = evt.get("type", "")

        if evt_type == "message":
            if evt.get("role") != "assistant":
                continue  # the CLI echoes the user prompt; nothing to emit
            content = evt.get("content", "")
            if not isinstance(content, str) or not content:
                continue

            if evt.get("delta"):
                if not text_open:
                    text_open = True
                    text_index = next_index
                    next_index += 1
                    text_buf = ""
                    yield StreamTaskMessageStart(
                        type="start",
                        index=text_index,
                        content=TextContent(type="text", author="agent", content=""),
                    )
                text_buf += content
                assert text_index is not None
                yield StreamTaskMessageDelta(
                    type="delta",
                    index=text_index,
                    delta=TextDelta(type="text", text_delta=content),
                )
                continue

            # A complete (non-delta) assistant message. If it materialises the
            # slot we are already streaming, just close the slot; otherwise
            # deliver it as its own Start + Delta + Done.
            if text_open and text_buf and content.startswith(text_buf):
                done = _close_text()
                if done is not None:
                    yield done
                continue
            done = _close_text()
            if done is not None:
                yield done
            msg_index = next_index
            next_index += 1
            yield StreamTaskMessageStart(
                type="start",
                index=msg_index,
                content=TextContent(type="text", author="agent", content=""),
            )
            yield StreamTaskMessageDelta(
                type="delta",
                index=msg_index,
                delta=TextDelta(type="text", text_delta=content),
            )
            yield StreamTaskMessageDone(type="done", index=msg_index)

        elif evt_type == "tool_use":
            done = _close_text()
            if done is not None:
                yield done
            tool_call_count += 1
            tool_id = evt.get("tool_id") or f"tool_{tool_call_count}"
            name = evt.get("tool_name") or "unknown"
            arguments = evt.get("parameters")
            if not isinstance(arguments, dict):
                arguments = {}
            msg_index = next_index
            next_index += 1
            yield StreamTaskMessageStart(
                type="start",
                index=msg_index,
                content=ToolRequestContent(
                    type="tool_request",
                    author="agent",
                    tool_call_id=str(tool_id),
                    name=str(name),
                    arguments=arguments,
                ),
            )
            yield StreamTaskMessageDone(type="done", index=msg_index)

        elif evt_type == "tool_result":
            done = _close_text()
            if done is not None:
                yield done
            tool_id = str(evt.get("tool_id") or "")
            is_error = evt.get("status") == "error"
            output = evt.get("output")
            if output is None:
                error = evt.get("error") or {}
                output = error.get("message", "") if isinstance(error, dict) else str(error)
            result_content: dict[str, Any] = {"result": _truncate(str(output))}
            if is_error:
                result_content["is_error"] = True
            msg_index = next_index
            next_index += 1
            yield StreamTaskMessageFull(
                type="full",
                index=msg_index,
                content=ToolResponseContent(
                    type="tool_response",
                    author="agent",
                    tool_call_id=tool_id,
                    name="",
                    content=result_content,
                ),
            )

        elif evt_type == "init":
            if on_init is not None:
                await on_init(evt)

        elif evt_type == "error":
            logger.warning(
                "gemini-cli: %s: %s",
                evt.get("severity", "error"),
                str(evt.get("message", ""))[:300],
            )

        elif evt_type == "result":
            done = _close_text()
            if done is not None:
                yield done
            if on_result is not None:
                await on_result(evt)

        else:
            logger.debug("gemini-cli: unhandled event type %r", evt_type)

    # Stream ended without a result event (truncated / interrupted): close the
    # slot so every Start has a matching Done.
    done = _close_text()
    if done is not None:
        yield done
