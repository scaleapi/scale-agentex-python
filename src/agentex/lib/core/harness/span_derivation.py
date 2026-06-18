"""Pure reducer: canonical StreamTaskMessage* stream -> span open/close signals.

Has no dependency on adk; unit-testable in isolation. Delivery adapters feed it
every event and act on the returned signals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from agentex.lib.core.harness.types import OpenSpan, CloseSpan, SpanSignal, StreamTaskMessage
from agentex.types.tool_request_delta import ToolRequestDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent


@dataclass
class _ToolReqMeta:
    tool_call_id: str
    name: str
    arguments: dict[str, object]
    args_buf: str = ""  # accumulated streamed argument fragments


class SpanDeriver:
    """Stateful reducer over the canonical stream.

    Tool span: open on Done of a ToolRequestContent index; close on matching
    ToolResponseContent by tool_call_id. Reasoning span: open on
    Start(ReasoningContent); close on that index's Done.

    Deliberate contracts:
      - A `Full(ToolResponseContent)` whose tool_call_id was never opened is
        ignored (no CloseSpan emitted).
      - A `Done` for an index that was never a tool_request/reasoning Start is
        ignored (no signal emitted).
      - Events with `index is None` are skipped entirely; without a stable index
        they cannot be reliably paired, and aliasing them to a sentinel would
        let unrelated None-indexed events cross-match.
      - `flush()` closes anything still open as incomplete; unclosed tool spans
        are emitted in the order they were opened.
    """

    def __init__(self) -> None:
        self._tool_by_index: dict[int, _ToolReqMeta] = {}
        self._reasoning_index_open: set[int] = set()
        # insertion-ordered set of open tool_call_ids (dict keys preserve order)
        self._open_tool_ids: dict[str, None] = {}

    def observe(self, event: StreamTaskMessage) -> list[SpanSignal]:
        if isinstance(event, StreamTaskMessageStart):
            return self._on_start(event)
        if isinstance(event, StreamTaskMessageDelta):
            return self._on_delta(event)
        if isinstance(event, StreamTaskMessageFull):
            return self._on_full(event)
        if isinstance(event, StreamTaskMessageDone):
            return self._on_done(event)
        return []

    def flush(self) -> list[SpanSignal]:
        """Close anything still open at end of stream, marked incomplete."""
        signals: list[SpanSignal] = []
        for tcid in list(self._open_tool_ids):
            signals.append(CloseSpan(key=tcid, output=None, is_complete=False))
        self._open_tool_ids.clear()
        for idx in sorted(self._reasoning_index_open):
            signals.append(CloseSpan(key=f"reasoning:{idx}", output=None, is_complete=False))
        self._reasoning_index_open.clear()
        return signals

    def _on_start(self, event: StreamTaskMessageStart) -> list[SpanSignal]:
        if event.index is None:
            return []
        idx = event.index
        content = event.content
        if isinstance(content, ToolRequestContent):
            self._tool_by_index[idx] = _ToolReqMeta(
                tool_call_id=content.tool_call_id,
                name=content.name,
                arguments=dict(content.arguments or {}),
            )
            return []
        if content.type == "reasoning":
            self._reasoning_index_open.add(idx)
            return [OpenSpan(key=f"reasoning:{idx}", kind="reasoning", name="reasoning", input={})]
        return []

    def _on_delta(self, event: StreamTaskMessageDelta) -> list[SpanSignal]:
        if event.index is None:
            return []
        idx = event.index
        delta = event.delta
        if isinstance(delta, ToolRequestDelta):
            meta = self._tool_by_index.get(idx)
            if meta is not None and delta.arguments_delta:
                meta.args_buf += delta.arguments_delta
        return []

    def _on_full(self, event: StreamTaskMessageFull) -> list[SpanSignal]:
        """Handle a Full event.

        A `Full(ToolRequestContent)` opens a tool span (keyed by tool_call_id)
        if it is not already open; the matching `Full(ToolResponseContent)`
        closes it. This handles harnesses (e.g. LangGraph) that emit tool calls
        as a single Full rather than Start+Done.
        """
        content = event.content
        if isinstance(content, ToolRequestContent):
            tcid = content.tool_call_id
            if tcid not in self._open_tool_ids:
                self._open_tool_ids[tcid] = None
                args = dict(content.arguments or {})
                return [OpenSpan(key=tcid, kind="tool", name=content.name, input=args)]
            return []
        if isinstance(content, ToolResponseContent):
            tcid = content.tool_call_id
            if tcid in self._open_tool_ids:
                self._open_tool_ids.pop(tcid, None)
                return [CloseSpan(key=tcid, output=content.content, is_complete=True)]
        return []

    def _on_done(self, event: StreamTaskMessageDone) -> list[SpanSignal]:
        if event.index is None:
            return []
        idx = event.index
        meta = self._tool_by_index.pop(idx, None)
        if meta is not None:
            args = meta.arguments
            if meta.args_buf:
                try:
                    args = json.loads(meta.args_buf)
                except json.JSONDecodeError:
                    args = {"_raw": meta.args_buf}
            self._open_tool_ids[meta.tool_call_id] = None
            return [OpenSpan(key=meta.tool_call_id, kind="tool", name=meta.name, input=args)]
        if idx in self._reasoning_index_open:
            self._reasoning_index_open.discard(idx)
            return [CloseSpan(key=f"reasoning:{idx}", output=None, is_complete=True)]
        return []
