"""LangChain callback handler that creates Agentex spans for LLM calls and tool executions."""
# ruff: noqa: ARG002
# Callback methods must accept all arguments defined by LangChain's AsyncCallbackHandler interface.

from __future__ import annotations

from uuid import UUID
from typing import Any, override

from langchain_core.outputs import LLMResult
from langchain_core.messages import BaseMessage
from langchain_core.callbacks import AsyncCallbackHandler

from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.adk._modules.tracing import TracingModule

logger = make_logger(__name__)


class AgentexLangGraphTracingHandler(AsyncCallbackHandler):
    """Async LangChain callback handler that records Agentex tracing spans.

    Creates child spans under a parent span for each LLM call and tool execution.
    Designed to be passed via ``config={"callbacks": [handler]}`` to LangGraph's
    ``graph.astream()`` or ``graph.ainvoke()``.

    Span hierarchy produced::

        <parent span>  (e.g. "message" turn-level span)
          ├── llm:<model>       (LLM call)
          ├── tool:<tool_name>  (tool execution)
          └── llm:<model>       (LLM call)
    """

    def __init__(
        self,
        trace_id: str,
        parent_span_id: str | None = None,
        tracing: TracingModule | None = None,
    ) -> None:
        super().__init__()
        self._trace_id = trace_id
        self._parent_span_id = parent_span_id
        # Lazily initialise TracingModule so the httpx client is created
        # inside the *running* event-loop (not at import/construction time).
        self._tracing_eager = tracing
        self._tracing_lazy: TracingModule | None = None
        # Map run_id → Span for in-flight spans
        self._spans: dict[UUID, Span] = {}

    @property
    def _tracing(self) -> TracingModule:
        if self._tracing_eager is not None:
            return self._tracing_eager
        if self._tracing_lazy is None:
            self._tracing_lazy = TracingModule()
        return self._tracing_lazy

    # ------------------------------------------------------------------
    # LLM lifecycle
    # ------------------------------------------------------------------

    @override
    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        model_name = (metadata or {}).get("ls_model_name", "") or _extract_model_name(serialized)
        span = await self._tracing.start_span(
            trace_id=self._trace_id,
            name=f"llm:{model_name}" if model_name else "llm",
            input=_serialize_messages(messages),
            parent_id=self._parent_span_id,
            data={"__span_type__": "COMPLETION"},
        )
        if span:
            self._spans[run_id] = span

    @override
    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.output = _serialize_llm_result(response)
        await self._tracing.end_span(trace_id=self._trace_id, span=span)

    @override
    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.output = {"error": str(error)}
        await self._tracing.end_span(trace_id=self._trace_id, span=span)

    # ------------------------------------------------------------------
    # Tool lifecycle
    # ------------------------------------------------------------------

    @override
    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "") or serialized.get("id", [""])[-1]
        span = await self._tracing.start_span(
            trace_id=self._trace_id,
            name=f"tool:{tool_name}" if tool_name else "tool",
            input={"input": input_str},
            parent_id=self._parent_span_id,
            data={"__span_type__": "CUSTOM"},
        )
        if span:
            self._spans[run_id] = span

    @override
    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.output = {"output": output}
        await self._tracing.end_span(trace_id=self._trace_id, span=span)

    @override
    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.output = {"error": str(error)}
        await self._tracing.end_span(trace_id=self._trace_id, span=span)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_model_name(serialized: dict[str, Any]) -> str:
    """Best-effort model name extraction from the serialized callback dict."""
    kwargs = serialized.get("kwargs", {})
    return kwargs.get("model_name", "") or kwargs.get("model", "")


def _serialize_messages(messages: list[list[BaseMessage]]) -> dict[str, Any]:
    """Serialize LangChain messages into a JSON-safe dict for the span input."""
    result: list[dict[str, Any]] = []
    for batch in messages:
        for msg in batch:
            entry: dict[str, Any] = {"type": msg.type, "content": msg.content}
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                entry["tool_calls"] = tool_calls
            result.append(entry)
    return {"messages": result}


def _serialize_llm_result(response: LLMResult) -> dict[str, Any]:
    """Serialize an LLMResult into a JSON-safe dict for the span output."""
    output: dict[str, Any] = {}
    if response.generations:
        last_gen = response.generations[-1]
        if last_gen:
            gen = last_gen[-1]
            msg = getattr(gen, "message", None)

            # For reasoning models, content is a list of typed blocks.
            # Extract text from the blocks instead of relying on gen.text.
            if msg and isinstance(msg.content, list):
                text_parts: list[str] = []
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                output["content"] = "".join(text_parts) if text_parts else gen.text
            else:
                output["content"] = gen.text

            if msg and hasattr(msg, "tool_calls") and msg.tool_calls:
                output["tool_calls"] = [{"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls]
    return output


def create_langgraph_tracing_handler(
    trace_id: str,
    parent_span_id: str | None = None,
) -> AgentexLangGraphTracingHandler:
    """Create a LangChain callback handler that records Agentex tracing spans.

    Pass the returned handler to LangGraph via ``config={"callbacks": [handler]}``.

    Args:
        trace_id: The trace ID (typically the task/thread ID).
        parent_span_id: Optional parent span ID to nest LLM/tool spans under.

    Returns:
        An ``AgentexLangGraphTracingHandler`` instance ready to use as a LangChain callback.
    """
    return AgentexLangGraphTracingHandler(
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )
