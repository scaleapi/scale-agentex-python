"""Codex event-stream parser tap for the unified harness surface.

Converts a ``codex exec --json`` newline-delimited event stream (already
produced by the golden agent's sandbox/subprocess orchestration) into the
Agentex canonical ``StreamTaskMessage*`` events.

SCOPE
-----
This module is a **pure parser**. It receives pre-produced codex events
(``str`` lines or already-decoded ``dict`` objects) and yields canonical
``StreamTaskMessage*`` events. All subprocess management, sandbox
provisioning, secret injection, and MCP orchestration remain in the golden
agent at
``teams/sgp/agents/golden_agent/project/harness/providers/codex.py``.

No deployable test agent is included here: running codex requires the
golden agent's sandbox environment and is out of scope for this library tap.

OUT OF SCOPE (document here so future callers are not surprised):
- Subprocess / sandbox management
- OPENAI_API_KEY / secret injection
- MCP server configuration (--config /tmp/codex_config.toml)
- ``codex exec resume`` session tracking
- ``scale_sandbox`` imports

CANONICAL MAPPING
-----------------
The table below lists every ``type`` field the codex exec JSON stream can
emit (from ``codex-rs/exec/src/exec_events.rs``) and its mapping.

Top-level event types
~~~~~~~~~~~~~~~~~~~~~
  thread.started          -> (no StreamTaskMessage; session_id captured
                              internally; surfaced via ``on_result`` callback)
  turn.started            -> (no StreamTaskMessage; turn was started before
                              codex launched; nothing to emit here)
  turn.completed          -> on_result(usage_dict, tool_count, reasoning_count)
                             yields no StreamTaskMessage (turn lifecycle is
                             managed by the activity layer)
  turn.failed             -> StreamTaskMessageFull(TextContent, error text)
  error                   -> StreamTaskMessageFull(TextContent, error text)

Item sub-types (item.started / item.updated / item.completed)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  agent_message           -> text deltas:
                               item.started / item.updated  -> StreamTaskMessageDelta(TextDelta)
                               item.completed               -> StreamTaskMessageDone
  reasoning               -> reasoning:
                               item.started                 -> StreamTaskMessageStart(ReasoningContent)
                               item.updated                 -> (no-op; final text arrives on completed)
                               item.completed               -> StreamTaskMessageFull(ReasoningContent)
  command_execution       -> tool request + response:
                               item.started                 -> StreamTaskMessageStart(ToolRequestContent)
                                                              + StreamTaskMessageDone
                               item.completed               -> StreamTaskMessageFull(ToolResponseContent)
  file_change             -> same as command_execution
                             NOTE: file_change may only emit item.completed (no started);
                             a synthetic ToolRequestContent Full is emitted before the response.
  mcp_tool_call           -> same as command_execution
  web_search              -> same as command_execution
  todo_list               -> same as command_execution
  collab_tool_call        -> same as command_execution
  error (item type)       -> StreamTaskMessageFull(TextContent, error text) on completed only

UNMAPPED / PARTIALLY MAPPED EVENTS
-----------------------------------
  thread.started:         session_id is extracted but not forwarded as a
                          StreamTaskMessage (no canonical content type for
                          session-lifecycle signals; captured in on_result).
  turn.started:           no-op; intentional (the caller owns turn lifecycle).
  turn.completed:         no StreamTaskMessage; usage is forwarded via
                          on_result so the caller can record it in a span
                          without this module needing to know about spans.
  item.updated (reasoning): the intermediate cumulative text is discarded;
                            only item.completed carries the final text.
  item.updated (tool):    tool item types other than agent_message do not
                          emit updates; item.started opens the request and
                          item.completed closes it.
"""

from __future__ import annotations

import json
from typing import Any, Callable, AsyncIterator

from agentex.lib.utils.logging import make_logger
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.task_message_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta

logger = make_logger(__name__)

# Canonical type alias matching the unified harness surface.
StreamTaskMessage = StreamTaskMessageStart | StreamTaskMessageDelta | StreamTaskMessageFull | StreamTaskMessageDone

_MAX_RESULT_LENGTH = 4000


def _truncate(text: str, max_len: int = _MAX_RESULT_LENGTH) -> str:
    return str(text)[:max_len]


def _tool_name_for(item_type: str, payload: dict[str, Any]) -> str:
    """Derive a canonical tool name from a codex item type."""
    if item_type == "command_execution":
        return "bash"
    if item_type == "file_change":
        return "file_change"
    if item_type == "mcp_tool_call":
        server = payload.get("server", "")
        tool = payload.get("tool", "")
        return f"{server}.{tool}" if (server or tool) else "mcp_tool_call"
    if item_type == "web_search":
        return "web_search"
    if item_type == "todo_list":
        return "todo_list"
    if item_type == "collab_tool_call":
        return "collab_tool_call"
    return item_type or "unknown"


def _tool_args_for(item_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Extract canonical arguments dict from a codex item payload."""
    if item_type == "command_execution":
        return {"command": payload.get("command", "")}
    if item_type == "file_change":
        return {"changes": payload.get("changes") or []}
    if item_type == "mcp_tool_call":
        args = payload.get("arguments")
        return args if isinstance(args, dict) else {"value": args}
    if item_type == "web_search":
        return {"query": payload.get("query", "")}
    if item_type == "todo_list":
        return {"items": payload.get("items") or []}
    return {}


def _tool_output_for(item_type: str, payload: dict[str, Any]) -> tuple[str, bool]:
    """Extract (result_text, is_error) from a completed codex tool item."""
    if item_type == "command_execution":
        out = payload.get("aggregated_output") or ""
        exit_code = payload.get("exit_code")
        is_error = exit_code is not None and exit_code != 0
        return _truncate(out), is_error
    if item_type == "mcp_tool_call":
        err = payload.get("error")
        if err:
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
            return _truncate(f"Error: {msg}"), True
        result = payload.get("result")
        if result is None:
            return "", False
        try:
            return _truncate(json.dumps(result)), False
        except (TypeError, ValueError):
            return _truncate(str(result)), False
    if item_type == "file_change":
        changes = payload.get("changes") or []
        status = payload.get("status", "")
        return f"status={status}, {len(changes)} changes", status == "failed"
    try:
        return _truncate(json.dumps(payload, default=str)), False
    except (TypeError, ValueError):
        return _truncate(str(payload)), False


def _error_full(message: str, next_index: int) -> StreamTaskMessageFull:
    """Emit a one-shot TextContent full message for an error."""
    return StreamTaskMessageFull(
        type="full",
        index=next_index,
        content=TextContent(
            type="text",
            author="agent",
            content=f"Error: {message}",
            format="plain",
        ),
    )


class _CodexStreamProcessor:
    """Stateful parser: consumes codex exec events, yields StreamTaskMessage*.

    Ported from the golden agent's ``_CodexEventProcessor`` in
    ``project/harness/providers/codex.py``, adapted to yield
    ``StreamTaskMessage*`` directly instead of ``HarnessEvent`` objects.

    State tracked:
    - ``_next_index``: monotonically increasing message index.
    - ``_text_index``: message index of the current open agent_message block.
    - ``_text_accumulated``: cumulative text per agent_message item_id.
    - ``_reasoning_index``: message index of the current open reasoning block.
    - ``_reasoning_text``: latest cumulative reasoning text per item_id.
    - ``_tool_open``: item_ids for which a ToolRequestContent Start was emitted
       but no ToolResponseContent Full yet.
    - ``_tool_item_types``: item_id -> item_type for open tool calls.
    """

    def __init__(self) -> None:
        self._next_index: int = 0

        # agent_message tracking
        self._text_index: dict[str, int] = {}
        self._text_accumulated: dict[str, str] = {}

        # reasoning tracking
        self._reasoning_index: dict[str, int] = {}
        self._reasoning_text: dict[str, str] = {}

        # tool tracking
        self._tool_open: set[str] = set()
        self._tool_item_types: dict[str, str] = {}

        # counters for on_result callback
        self.tool_call_count: int = 0
        self.reasoning_count: int = 0
        self.session_id: str | None = None

    def _alloc(self) -> int:
        idx = self._next_index
        self._next_index += 1
        return idx

    def process(self, evt: dict[str, Any]) -> list[StreamTaskMessage]:
        evt_type = evt.get("type", "")

        if evt_type == "thread.started":
            sid = evt.get("thread_id") or ""
            if sid:
                self.session_id = sid
            return []

        if evt_type == "turn.started":
            # The activity layer owns turn lifecycle; nothing to emit.
            return []

        if evt_type == "turn.completed":
            # Usage forwarded via on_result callback (not a StreamTaskMessage).
            return []

        if evt_type == "turn.failed":
            err = evt.get("error") or {}
            msg = err.get("message", "codex turn failed") if isinstance(err, dict) else str(err)
            return [_error_full(f"Codex turn failed: {msg}", self._alloc())]

        if evt_type == "error":
            return [_error_full(evt.get("message", "codex error"), self._alloc())]

        if evt_type in ("item.started", "item.updated", "item.completed"):
            item = evt.get("item") or {}
            return self._handle_item(evt_type, item)

        logger.debug("[codex] unhandled event type=%s", evt_type)
        return []

    def _handle_item(self, evt_type: str, item: dict[str, Any]) -> list[StreamTaskMessage]:
        item_id = item.get("id") or ""
        item_type = item.get("type") or ""
        out: list[StreamTaskMessage] = []

        if item_type == "agent_message":
            current = item.get("text") or ""
            previous = self._text_accumulated.get(item_id, "")

            if evt_type in ("item.started", "item.updated"):
                if item_id not in self._text_index:
                    idx = self._alloc()
                    self._text_index[item_id] = idx
                    out.append(
                        StreamTaskMessageStart(
                            type="start",
                            index=idx,
                            content=TextContent(
                                type="text",
                                author="agent",
                                content="",
                            ),
                        )
                    )
                idx = self._text_index[item_id]
                delta = ""
                if current.startswith(previous) and len(current) > len(previous):
                    delta = current[len(previous) :]
                elif current and current != previous:
                    delta = current
                if delta:
                    out.append(
                        StreamTaskMessageDelta(
                            type="delta",
                            index=idx,
                            delta=TextDelta(type="text", text_delta=delta),
                        )
                    )
                self._text_accumulated[item_id] = current

            elif evt_type == "item.completed":
                if item_id not in self._text_index:
                    idx = self._alloc()
                    self._text_index[item_id] = idx
                    out.append(
                        StreamTaskMessageStart(
                            type="start",
                            index=idx,
                            content=TextContent(
                                type="text",
                                author="agent",
                                content="",
                            ),
                        )
                    )
                idx = self._text_index[item_id]
                delta = ""
                if current.startswith(previous) and len(current) > len(previous):
                    delta = current[len(previous) :]
                elif current and current != previous:
                    delta = current
                if delta:
                    out.append(
                        StreamTaskMessageDelta(
                            type="delta",
                            index=idx,
                            delta=TextDelta(type="text", text_delta=delta),
                        )
                    )
                out.append(StreamTaskMessageDone(type="done", index=idx))
                self._text_accumulated[item_id] = current

        elif item_type == "reasoning":
            current = item.get("text") or ""

            if evt_type == "item.started":
                idx = self._alloc()
                self._reasoning_index[item_id] = idx
                self._reasoning_text[item_id] = current
                out.append(
                    StreamTaskMessageStart(
                        type="start",
                        index=idx,
                        content=ReasoningContent(
                            type="reasoning",
                            author="agent",
                            summary=[],
                            content=[],
                            style="active",
                        ),
                    )
                )
                if current:
                    out.append(
                        StreamTaskMessageDelta(
                            type="delta",
                            index=idx,
                            delta=ReasoningContentDelta(
                                type="reasoning_content",
                                content_index=0,
                                content_delta=current,
                            ),
                        )
                    )

            elif evt_type == "item.updated":
                # Accumulate silently; final text arrives on item.completed.
                self._reasoning_text[item_id] = current

            elif evt_type == "item.completed":
                text = current or self._reasoning_text.get(item_id, "")
                idx = self._reasoning_index.get(item_id)
                if text:
                    self.reasoning_count += 1
                    summary = text.strip().split("\n", 1)[0][:300]
                    final_content = ReasoningContent(
                        type="reasoning",
                        author="agent",
                        summary=[summary],
                        content=[text],
                        style="static",
                    )
                    if idx is not None:
                        out.append(
                            StreamTaskMessageFull(
                                type="full",
                                index=idx,
                                content=final_content,
                            )
                        )
                    else:
                        # No started event was seen; emit a standalone Full.
                        out.append(
                            StreamTaskMessageFull(
                                type="full",
                                index=self._alloc(),
                                content=final_content,
                            )
                        )
                elif idx is not None:
                    # Empty reasoning block — still need to close with a Done.
                    out.append(StreamTaskMessageDone(type="done", index=idx))

        elif item_type in (
            "command_execution",
            "file_change",
            "mcp_tool_call",
            "web_search",
            "todo_list",
            "collab_tool_call",
        ):
            tool_call_id = item_id or f"codex_tool_{self.tool_call_count + 1}"

            if evt_type == "item.started":
                self.tool_call_count += 1
                self._tool_open.add(item_id)
                self._tool_item_types[item_id] = item_type
                name = _tool_name_for(item_type, item)
                args = _tool_args_for(item_type, item)
                req_idx = self._alloc()
                out.append(
                    StreamTaskMessageStart(
                        type="start",
                        index=req_idx,
                        content=ToolRequestContent(
                            type="tool_request",
                            author="agent",
                            tool_call_id=tool_call_id,
                            name=name,
                            arguments=args,
                        ),
                    )
                )
                out.append(StreamTaskMessageDone(type="done", index=req_idx))

            elif evt_type == "item.completed":
                # file_change items may only emit item.completed (no started).
                if item_id not in self._tool_open:
                    self.tool_call_count += 1
                    self._tool_open.add(item_id)
                    self._tool_item_types[item_id] = item_type
                    name = _tool_name_for(item_type, item)
                    args = _tool_args_for(item_type, item)
                    req_idx = self._alloc()
                    out.append(
                        StreamTaskMessageFull(
                            type="full",
                            index=req_idx,
                            content=ToolRequestContent(
                                type="tool_request",
                                author="agent",
                                tool_call_id=tool_call_id,
                                name=name,
                                arguments=args,
                            ),
                        )
                    )

                actual_type = self._tool_item_types.get(item_id, item_type)
                result_text, is_error = _tool_output_for(actual_type, item)
                name = _tool_name_for(actual_type, item)
                resp_content: dict[str, Any] = {"result": result_text}
                if is_error:
                    resp_content["is_error"] = True
                out.append(
                    StreamTaskMessageFull(
                        type="full",
                        index=self._alloc(),
                        content=ToolResponseContent(
                            type="tool_response",
                            author="agent",
                            tool_call_id=tool_call_id,
                            name=name,
                            content=resp_content,
                        ),
                    )
                )
                self._tool_open.discard(item_id)

        elif item_type == "error":
            if evt_type == "item.completed":
                out.append(_error_full(item.get("message", "codex item error"), self._alloc()))

        else:
            logger.debug("[codex] unhandled item type=%s evt=%s", item_type, evt_type)

        return out


async def convert_codex_to_agentex_events(
    events: AsyncIterator[str | dict[str, Any]],
    on_result: Callable[[dict[str, Any]], None] | None = None,
) -> AsyncIterator[StreamTaskMessage]:
    """Convert a ``codex exec --json`` event stream into Agentex stream events.

    This is a pure parser tap. The caller must supply ``events`` as an async
    iterator of either raw newline-delimited JSON strings or pre-decoded dicts.
    No subprocess or sandbox management is done here.

    Args:
        events: Async iterator of ``str`` (newline-delimited JSON lines) or
            ``dict`` (pre-decoded event objects) as produced by the codex CLI's
            ``--json`` flag via sandbox stdout.
        on_result: Optional callback invoked once when a ``turn.completed``
            event is seen. Receives a dict with keys:
                ``usage``           — the raw codex usage dict (or None)
                ``session_id``      — the codex thread_id (or None)
                ``tool_call_count`` — int
                ``reasoning_count`` — int
            Use this to record turn-level metrics / usage in the caller's span
            without coupling this module to span/tracing APIs.

    Yields:
        Canonical ``StreamTaskMessage*`` events (Start/Delta/Full/Done) with
        ``TextContent``, ``ReasoningContent``, ``ToolRequestContent``, or
        ``ToolResponseContent`` payloads.

    MAPPING (abbreviated — see module docstring for the full table)
        thread.started          -> no event; session_id captured for on_result
        turn.started            -> no event
        turn.completed          -> no event; triggers on_result callback
        turn.failed / error     -> StreamTaskMessageFull(TextContent, error)
        agent_message           -> Start + Deltas + Done
        reasoning               -> Start + Full(ReasoningContent)
        command_execution       -> Start(ToolRequest)+Done + Full(ToolResponse)
        file_change             -> Full(ToolRequest) + Full(ToolResponse)
        mcp_tool_call           -> Start(ToolRequest)+Done + Full(ToolResponse)
        web_search / todo_list  -> Start(ToolRequest)+Done + Full(ToolResponse)
        collab_tool_call        -> Start(ToolRequest)+Done + Full(ToolResponse)
    """
    processor = _CodexStreamProcessor()
    _pending_usage: dict[str, Any] | None = None

    async for raw in events:
        if isinstance(raw, dict):
            evt = raw
        else:
            line = raw.strip() if isinstance(raw, str) else ""
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("[codex] non-JSON line: %s", line[:100])
                continue

        # Capture usage before processing so on_result can fire after flush.
        if evt.get("type") == "turn.completed":
            usage = evt.get("usage")
            _pending_usage = usage if isinstance(usage, dict) else None

        messages = processor.process(evt)
        for msg in messages:
            yield msg

    if on_result is not None:
        on_result(
            {
                "usage": _pending_usage,
                "session_id": processor.session_id,
                "tool_call_count": processor.tool_call_count,
                "reasoning_count": processor.reasoning_count,
            }
        )
