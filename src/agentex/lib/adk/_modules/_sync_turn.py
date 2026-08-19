"""One traced turn on the sync (non-Temporal) OpenAI Agents path.

Agents on this path call ``Runner.run_streamed`` themselves, so nothing owns the
turn and no span covers it: the provider only spans the inference call, and every
span is emitted with no parent. A trace is therefore a flat list of fragments
whose durations do not add up to the turn, and tool time is missing entirely.

``run_turn_streamed`` owns the turn instead. It opens one root span, hangs the
tool spans off it, drains anything left open, and closes the root when the stream
is done, so the root's width is the turn's real latency.
"""

from __future__ import annotations

from typing import Any, AsyncIterator
from datetime import timedelta

from agents import Agent, Runner, RunConfig

from agentex.lib.utils.logging import make_logger
from agentex.lib.adk._modules._sync_tracing_hooks import SyncTracingHooks

logger = make_logger(__name__)

_TRACE_TIMEOUT = timedelta(seconds=5)


def _get_adk() -> Any:
    from agentex.lib import adk

    return adk


async def run_turn_streamed(
    starting_agent: Agent,
    input: Any,
    *,
    trace_id: str | None = None,
    task_id: str | None = None,
    run_config: RunConfig | None = None,
    max_turns: int | None = None,
    span_name: str = "turn",
) -> AsyncIterator[Any]:
    """Stream one agent turn, wrapped in a root span with tool spans beneath it.

    Yields the SDK's raw stream events untouched, so callers keep whatever event
    conversion they already do.

    Tracing is best-effort throughout: if the backend is unreachable the turn
    still runs and still streams.
    """
    root_span = None
    if trace_id:
        try:
            root_span = await _get_adk().tracing.start_span(
                trace_id=trace_id,
                task_id=task_id,
                name=span_name,
                input={"agent": starting_agent.name},
                start_to_close_timeout=_TRACE_TIMEOUT,
            )
        except Exception as e:  # noqa: BLE001 - tracing is best-effort
            logger.warning(f"[tracing] turn start_span failed (non-fatal): {e}")

    hooks = SyncTracingHooks(
        trace_id=trace_id,
        # Tool spans nest under the turn, which is what lets the UI draw a
        # waterfall instead of a flat list.
        parent_span_id=getattr(root_span, "id", None),
        task_id=task_id,
    )

    run_kwargs: dict[str, Any] = {"hooks": hooks}
    if run_config is not None:
        run_kwargs["run_config"] = run_config
    if max_turns is not None:
        run_kwargs["max_turns"] = max_turns

    try:
        result = Runner.run_streamed(starting_agent, input, **run_kwargs)
        async for event in result.stream_events():
            yield event
    finally:
        # A turn that dies mid-tool (max-turns, cancellation, an SDK error) never
        # fires the matching end hook, so drain before closing the root.
        await hooks.close_open_tool_spans()
        if root_span is not None and trace_id:
            try:
                await _get_adk().tracing.end_span(
                    trace_id=trace_id,
                    span=root_span,
                    start_to_close_timeout=_TRACE_TIMEOUT,
                )
            except Exception as e:  # noqa: BLE001 - tracing is best-effort
                logger.warning(f"[tracing] turn end_span failed (non-fatal): {e}")
