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
    # Full text of each block already delivered via stream_event deltas, so the
    # materialised assistant envelope does not re-emit it. Matched by CONTENT,
    # not block index: a single streamed message can arrive as several assistant
    # envelopes (e.g. a thinking block, then the text block), and the per-block
    # numeric index does not survive that split while the text does. Each match
    # is consumed (one entry removed) so a genuinely repeated later block — a new
    # turn that happens to emit identical text — is still delivered.
    _streamed_texts: list[str] = []
    _streamed_thinkings: list[str] = []

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

            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")

                if block_type == "text":
                    text = block.get("text", "")
                    if not text:
                        continue
                    # Skip blocks already delivered via stream_event deltas. Two
                    # cases: (1) the streamed block already finished — its full
                    # text is recorded in _streamed_texts; (2) the materialised
                    # envelope arrives INTERLEAVED, mid-stream, before the streamed
                    # block's content_block_stop records its buffer — the still-open
                    # block's partial buffer is a prefix of this full text.
                    if text in _streamed_texts:
                        _streamed_texts.remove(text)
                        continue
                    if _text_open and _text_buf and text.startswith(_text_buf):
                        continue
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
                    thinking_text = block.get("thinking", "")
                    if thinking_text:
                        # Skip blocks already delivered via stream_event deltas.
                        # Same two cases as text above: finished streamed block
                        # (recorded), or an interleaved materialised envelope whose
                        # text the still-open streamed buffer is a prefix of.
                        if thinking_text in _streamed_thinkings:
                            _streamed_thinkings.remove(thinking_text)
                            continue
                        if _thinking_open and _thinking_buf and thinking_text.startswith(_thinking_buf):
                            continue
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

        # -----------------------------------------------------------------------
        # stream_event — incremental streaming deltas
        # -----------------------------------------------------------------------
        elif evt_type == "stream_event":
            se = evt.get("event") or {}
            se_type = se.get("type", "")

            if se_type == "content_block_start":
                block = se.get("content_block") or {}
                btype = block.get("type")

                if btype == "thinking":
                    _thinking_open = True
                    _thinking_buf = ""
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
                    _thinking_open = False
                    # Record the streamed thinking so the materialised assistant
                    # envelope doesn't re-emit it. Skip empties: a block_start with
                    # no deltas leaves the assistant envelope free to fill the text.
                    if _thinking_buf:
                        _streamed_thinkings.append(_thinking_buf)
                    _thinking_buf = ""
                    if _thinking_index is not None:
                        yield StreamTaskMessageDone(type="done", index=_thinking_index)
                    _thinking_index = None
                elif _text_open:
                    _text_open = False
                    # Record the streamed text for content-based dedup against the
                    # materialised assistant envelope (see _streamed_texts).
                    if _text_buf:
                        _streamed_texts.append(_text_buf)
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
