"""Claude Code stream-json parser tap for the unified harness surface.

Converts the newline-delimited JSON envelopes emitted by
``claude -p --output-format stream-json`` into the canonical
``StreamTaskMessage*`` stream consumed by the Agentex harness.

Envelope → canonical mapping
-----------------------------
system/init
    Ignored at this layer (session_id tracking is a provider concern).

assistant / user  (content blocks)
    text block           → Start(TextContent) + Delta(TextDelta)* + Done
    thinking block       → Start(ReasoningContent) + Delta(ReasoningContentDelta)* + Done
    tool_use block       → Start(ToolRequestContent) + Done   (Full args in Start content)
    tool_result block    → Full(ToolResponseContent)

stream_event / content_block_start
    type=text            → Start(TextContent, empty)
    type=thinking        → Start(ReasoningContent, empty)

stream_event / content_block_delta
    type=text_delta      → Delta(TextDelta)
    type=thinking_delta  → Delta(ReasoningContentDelta)

stream_event / content_block_stop
    (text open)          → Done
    (thinking open)      → Done  (full text known here; update Full via Full event first)

result
    Fires ``on_result`` with the raw envelope so the caller can capture
    usage and cost. No StreamTaskMessage is emitted for the result itself.

Out of scope
------------
No deployable test agent is provided. claude-code requires the golden
agent's sandbox/subprocess/secret/MCP orchestration to produce the stream.
Live coverage is the golden agent, which will adopt this tap. Do NOT add an
examples/ agent or CI live-matrix row for claude-code.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Awaitable, AsyncIterator

from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta

logger = make_logger(__name__)

_MAX_RESULT_LENGTH = 4000


def _truncate(text: str) -> str:
    return str(text)[:_MAX_RESULT_LENGTH]


def _extract_summary(text: str, max_len: int = 300) -> str:
    return text.strip().split("\n", 1)[0][:max_len]


async def convert_claude_code_to_agentex_events(
    lines: AsyncIterator[str | dict[str, Any]],
    on_result: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> AsyncIterator[StreamTaskMessageStart | StreamTaskMessageDelta | StreamTaskMessageFull | StreamTaskMessageDone]:
    """Convert a claude-code ``stream-json`` line stream into Agentex ``StreamTaskMessage*`` events.

    Each item in ``lines`` is either a raw JSON string (as read from the CLI's
    stdout) or an already-parsed dict. Empty strings are skipped; unparseable
    JSON is logged and skipped.

    ``on_result`` is called with the ``result`` envelope when it arrives so the
    caller can capture usage and cost. It is awaited before the generator
    continues. When ``None``, the result envelope is silently dropped.

    Envelope → canonical mapping is documented in this module's docstring.
    """
    next_index = 0
    tool_call_count = 0

    # Streaming state for content_block_start / content_block_delta /
    # content_block_stop triples.
    _thinking_open = False
    _thinking_buf = ""
    _thinking_index: int | None = None
    _text_open = False
    _text_buf = ""
    _text_index: int | None = None
    # Track which assistant-message block indices were already streamed via
    # stream_event triples. Those blocks must not be re-emitted when the full
    # assistant message arrives. Reset at each message boundary (see below) so a
    # later turn's block indices don't collide with an earlier turn's.
    _streamed_block_indexes: set[int] = set()
    # Once-guard so a thinking block's pending index is claimed on its first
    # thinking_delta only. Reset per turn alongside _streamed_block_indexes.
    _saw_thinking_stream = False
    # For deferred ReasoningStarted: if a content_block_start(thinking) arrives
    # but no thinking_delta ever follows, the final assistant block's thinking
    # field fills the reasoning content instead.
    _pending_thinking_block_index: int | None = None

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
                logger.debug("claude-code: skipping non-JSON line: %r", line[:120])
                continue

        evt_type = evt.get("type", "")

        # -----------------------------------------------------------------------
        # assistant / user — materialised content blocks
        # -----------------------------------------------------------------------
        if evt_type in ("assistant", "user"):
            msg = evt.get("message", {})
            blocks = msg.get("content", [])
            if not isinstance(blocks, list):
                blocks = [blocks]

            for idx, block in enumerate(blocks):
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")

                if block_type == "text":
                    # Skip only the specific blocks already delivered via
                    # stream_event deltas (per-block, not a turn-wide latch).
                    if idx in _streamed_block_indexes:
                        continue
                    text = block.get("text", "")
                    if text:
                        msg_index = next_index
                        next_index += 1
                        yield StreamTaskMessageStart(
                            type="start",
                            index=msg_index,
                            content=TextContent(
                                type="text",
                                author="agent",
                                content="",
                            ),
                        )
                        yield StreamTaskMessageDelta(
                            type="delta",
                            index=msg_index,
                            delta=TextDelta(type="text", text_delta=text),
                        )
                        yield StreamTaskMessageDone(type="done", index=msg_index)

                elif block_type == "thinking":
                    # Skip only the specific blocks already delivered via
                    # stream_event deltas (per-block, not a turn-wide latch).
                    if idx in _streamed_block_indexes:
                        continue
                    thinking_text = block.get("thinking", "")
                    if thinking_text:
                        summary = _extract_summary(thinking_text)
                        msg_index = next_index
                        next_index += 1
                        yield StreamTaskMessageStart(
                            type="start",
                            index=msg_index,
                            content=ReasoningContent(
                                type="reasoning",
                                author="agent",
                                summary=[summary],
                                content=[],
                                style="active",
                            ),
                        )
                        yield StreamTaskMessageDelta(
                            type="delta",
                            index=msg_index,
                            delta=ReasoningContentDelta(
                                type="reasoning_content",
                                content_index=0,
                                content_delta=thinking_text,
                            ),
                        )
                        yield StreamTaskMessageDone(type="done", index=msg_index)

                elif block_type == "tool_use":
                    tool_call_count += 1
                    tool_id = block.get("id", f"tool_{tool_call_count}")
                    name = block.get("name", "unknown")
                    arguments = block.get("input", {})
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
                            tool_call_id=tool_id,
                            name=name,
                            arguments=arguments,
                        ),
                    )
                    yield StreamTaskMessageDone(type="done", index=msg_index)

                elif block_type == "tool_result":
                    tool_id = block.get("tool_use_id", "")
                    content = block.get("content", "")
                    is_error = block.get("is_error", False)
                    if isinstance(content, list):
                        content = "\n".join(b.get("text", str(b)) if isinstance(b, dict) else str(b) for b in content)
                    result_str = _truncate(str(content))
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
                            content={"result": result_str, **({"is_error": True} if is_error else {})},
                        ),
                    )

            # End of a materialised message: reset per-turn streaming dedup state
            # so the next turn's stream_event indices start clean. Without this,
            # a block index streamed in an earlier turn would linger in the set
            # and silently drop a later turn's non-streamed block at that index.
            _streamed_block_indexes = set()
            _saw_thinking_stream = False

        # -----------------------------------------------------------------------
        # stream_event — incremental streaming deltas
        # -----------------------------------------------------------------------
        elif evt_type == "stream_event":
            se = evt.get("event") or {}
            se_type = se.get("type", "")
            block_index = se.get("index")

            if se_type == "content_block_start":
                block = se.get("content_block") or {}
                btype = block.get("type")

                if btype == "thinking":
                    _thinking_open = True
                    _thinking_buf = ""
                    # Defer marking the block as streamed until we actually
                    # receive a thinking_delta. Some configurations emit a
                    # thinking block_start but no deltas — in that case we want
                    # the final assistant-message handler to fill the text.
                    _pending_thinking_block_index = block_index if isinstance(block_index, int) else None
                    msg_index = next_index
                    next_index += 1
                    _thinking_index = msg_index
                    yield StreamTaskMessageStart(
                        type="start",
                        index=msg_index,
                        content=ReasoningContent(
                            type="reasoning",
                            author="agent",
                            summary=[],
                            content=[],
                            style="active",
                        ),
                    )

                elif btype == "text":
                    _text_open = True
                    _text_buf = ""
                    if isinstance(block_index, int):
                        _streamed_block_indexes.add(block_index)
                    msg_index = next_index
                    next_index += 1
                    _text_index = msg_index
                    yield StreamTaskMessageStart(
                        type="start",
                        index=msg_index,
                        content=TextContent(
                            type="text",
                            author="agent",
                            content="",
                        ),
                    )

            elif se_type == "content_block_delta":
                delta = se.get("delta") or {}
                dtype = delta.get("type")

                if dtype == "thinking_delta":
                    chunk = delta.get("thinking", "")
                    if chunk and _thinking_open:
                        if not _saw_thinking_stream:
                            _saw_thinking_stream = True
                            # Now mark the block as claimed so the assistant
                            # message handler won't re-emit it.
                            if _pending_thinking_block_index is not None:
                                _streamed_block_indexes.add(_pending_thinking_block_index)
                        _thinking_buf += chunk
                        if _thinking_index is not None:
                            yield StreamTaskMessageDelta(
                                type="delta",
                                index=_thinking_index,
                                delta=ReasoningContentDelta(
                                    type="reasoning_content",
                                    content_index=0,
                                    content_delta=chunk,
                                ),
                            )

                elif dtype == "text_delta":
                    chunk = delta.get("text", "")
                    if chunk and _text_open:
                        _text_buf += chunk
                        if _text_index is not None:
                            yield StreamTaskMessageDelta(
                                type="delta",
                                index=_text_index,
                                delta=TextDelta(type="text", text_delta=chunk),
                            )

            elif se_type == "content_block_stop":
                if _thinking_open:
                    full_text = _thinking_buf
                    _thinking_open = False
                    _thinking_buf = ""
                    _pending_thinking_block_index = None
                    # Reset the once-guard per thinking block: a turn can stream a
                    # second thinking block, and without this the guard stays True,
                    # the second block's index is never claimed, and the final
                    # assistant envelope re-emits it (duplicate Start/Delta/Done).
                    _saw_thinking_stream = False
                    if _thinking_index is not None:
                        yield StreamTaskMessageDone(type="done", index=_thinking_index)
                    _thinking_index = None
                elif _text_open:
                    _text_open = False
                    _text_buf = ""
                    if _text_index is not None:
                        yield StreamTaskMessageDone(type="done", index=_text_index)
                    _text_index = None

        # -----------------------------------------------------------------------
        # system / init — session metadata (ignored at this layer)
        # -----------------------------------------------------------------------
        elif evt_type == "system":
            # Session ID tracking and MCP status logging are provider concerns.
            # This pure parser layer intentionally emits nothing for system events.
            pass

        # -----------------------------------------------------------------------
        # result — carries usage + cost; fired to on_result, not emitted as msgs
        # -----------------------------------------------------------------------
        elif evt_type == "result":
            if on_result is not None:
                await on_result(evt)

        else:
            logger.debug("claude-code: unhandled envelope type %r", evt_type)
