"""Pure reducer: canonical StreamTaskMessage* stream -> span open/close signals.

Has no dependency on adk; unit-testable in isolation. Delivery adapters feed it
every event and act on the returned signals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agentex.types.task_message_update import (
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)

from agentex.lib.core.harness.types import CloseSpan, OpenSpan, SpanSignal, StreamTaskMessage


@dataclass
class _ToolReqMeta:
    tool_call_id: str
    name: str
    arguments: dict[str, Any]
    args_buf: str = ""  # accumulated streamed argument fragments


class SpanDeriver:
    """Stateful reducer over the canonical stream.

    Tool span: open on Done of a ToolRequestContent index; close on matching
    ToolResponseContent by tool_call_id. Reasoning span: open on
    Start(ReasoningContent); close on that index's Done.
    """

    def __init__(self) -> None:
        self._tool_by_index: dict[int, _ToolReqMeta] = {}
        self._reasoning_index_open: set[int] = set()
        self._open_tool_ids: set[str] = set()

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
        content = event.content
        idx = event.index if event.index is not None else -1
        ctype = getattr(content, "type", None)
        if ctype == "tool_request":
            self._tool_by_index[idx] = _ToolReqMeta(
                tool_call_id=content.tool_call_id,
                name=content.name,
                arguments=dict(content.arguments or {}),
            )
            return []
        if ctype == "reasoning":
            self._reasoning_index_open.add(idx)
            return [OpenSpan(key=f"reasoning:{idx}", kind="reasoning", name="reasoning", input={})]
        return []

    def _on_delta(self, event: StreamTaskMessageDelta) -> list[SpanSignal]:
        idx = event.index if event.index is not None else -1
        delta = event.delta
        if delta is not None and getattr(delta, "type", None) == "tool_request":
            meta = self._tool_by_index.get(idx)
            if meta is not None and delta.arguments_delta:
                meta.args_buf += delta.arguments_delta
        return []

    def _on_full(self, event: StreamTaskMessageFull) -> list[SpanSignal]:
        content = event.content
        if getattr(content, "type", None) == "tool_response":
            tcid = content.tool_call_id
            if tcid in self._open_tool_ids:
                self._open_tool_ids.discard(tcid)
                return [CloseSpan(key=tcid, output=content.content, is_complete=True)]
        return []

    def _on_done(self, event: StreamTaskMessageDone) -> list[SpanSignal]:
        idx = event.index if event.index is not None else -1
        meta = self._tool_by_index.pop(idx, None)
        if meta is not None:
            args = meta.arguments
            if meta.args_buf:
                try:
                    args = json.loads(meta.args_buf)
                except json.JSONDecodeError:
                    args = {"_raw": meta.args_buf}
            self._open_tool_ids.add(meta.tool_call_id)
            return [OpenSpan(key=meta.tool_call_id, kind="tool", name=meta.name, input=args)]
        if idx in self._reasoning_index_open:
            self._reasoning_index_open.discard(idx)
            return [CloseSpan(key=f"reasoning:{idx}", output=None, is_complete=True)]
        return []
