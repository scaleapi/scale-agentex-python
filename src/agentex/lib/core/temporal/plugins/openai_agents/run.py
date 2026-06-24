"""``run_turn`` — the unified entry point for the OpenAI Agents Temporal harness.

This is the ``Runner.run`` analogue of the CLI harness's
``UnifiedEmitter.auto_send_turn``: it owns the repeatable per-turn concerns so
agents don't hand-roll them.

What it does:

1. Runs the agent via ``Runner.run`` with hooks that emit each tool call exactly
   ONCE. The ``TemporalStreamingModelProvider`` already streams the tool-call
   message from the model output, so the hooks are wired with
   ``emit_messages=False`` to avoid the double-post; they still trace tool calls
   (input + output) and emit token-usage metrics.
2. Normalizes token usage off the run result into a harness-independent
   ``TurnUsage`` so callers can attach it to the turn span / task metadata,
   matching what the CLI harness reports.

What it deliberately does NOT do: sandboxing. Sandbox provisioning is a
composable concern carried on ``RunConfig`` (the SDK's ``SandboxRunConfig``) and
is passed straight through. Agent-specific lifecycle UI (e.g. surfacing sandbox
provisioning as a tool card) belongs in a caller-supplied ``hooks`` subclass,
not here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from dataclasses import dataclass

from agents import Runner

from agentex.lib.utils.logging import make_logger
from agentex.lib.core.harness.types import TurnUsage
from agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks import TemporalStreamingHooks

if TYPE_CHECKING:
    from agents import RunHooks, RunConfig
    from agents.result import RunResult

logger = make_logger(__name__)

# Mirror the OpenAI Agents SDK default; callers can override per turn.
_DEFAULT_MAX_TURNS = 10


@dataclass
class OpenAIAgentsTurnResult:
    """The raw SDK run result plus normalized agentex usage.

    The raw ``result`` is kept so callers retain ``final_output``,
    ``to_input_list()`` and any provider extras (e.g. sandbox resume state);
    ``usage`` is the harness-independent token/cost summary for the turn span.
    """

    result: "RunResult"
    usage: TurnUsage

    @property
    def final_output(self) -> Any:
        return self.result.final_output


def _extract_turn_usage(result: "RunResult", *, model: str | None = None) -> TurnUsage:
    """Map the SDK's aggregated ``context_wrapper.usage`` onto ``TurnUsage``.

    Tolerant of a missing/partial Usage shape (non-OpenAI providers routed via
    litellm may omit the nested token details) — absent fields stay None.
    """
    usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
    if usage is None:
        return TurnUsage(model=model)

    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return TurnUsage(
        model=model,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
        cached_input_tokens=getattr(input_details, "cached_tokens", None),
        reasoning_tokens=getattr(output_details, "reasoning_tokens", None),
        num_llm_calls=getattr(usage, "requests", None),
    )


async def run_turn(
    starting_agent: Any,
    input: Any,
    *,
    task_id: str,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    run_config: "RunConfig | None" = None,
    hooks: "RunHooks | None" = None,
    model: str | None = None,
    max_turns: int = _DEFAULT_MAX_TURNS,
) -> OpenAIAgentsTurnResult:
    """Run one agent turn and return the result plus normalized usage.

    Args:
        starting_agent: The agent to run.
        input: The input list / string passed to ``Runner.run``.
        task_id: AgentEx task id for streaming.
        trace_id: When set, tool calls are traced to SGP (input + output). Only
            applied when ``hooks`` is omitted (it flows into the default
            ``TemporalStreamingHooks``). Ignored when you pass your own ``hooks``
            — see ``hooks`` below.
        parent_span_id: Parent span for the per-tool spans (typically the turn
            span). Same caveat as ``trace_id``: only applied to the default hooks.
        run_config: Forwarded to ``Runner.run`` verbatim (carries the model
            provider and any ``SandboxRunConfig``). Left untouched here.
        hooks: Optional hooks override. When omitted, a default
            ``TemporalStreamingHooks(emit_tool_requests=False, ...)`` is used so
            the streaming model is the sole tool-REQUEST emitter while the hooks
            still emit tool RESPONSES (the model does not), and ``trace_id`` /
            ``parent_span_id`` are forwarded into it. When you pass your own
            subclass (also with ``emit_tool_requests=False``) to add agent-specific
            lifecycle behavior such as a sandbox-ready card, ``trace_id`` and
            ``parent_span_id`` are NOT applied for you — pass them to your
            subclass's constructor yourself if you want tool spans traced.
        model: Model name recorded on the returned usage; derived from the agent
            when not supplied.
        max_turns: Forwarded to ``Runner.run``.

    Returns:
        OpenAIAgentsTurnResult with the raw run result and normalized usage.
    """
    if hooks is None:
        hooks = TemporalStreamingHooks(
            task_id=task_id,
            # The streaming model already posts the tool REQUEST, so suppress it
            # here (no double-post) — but keep responses, which the model does not
            # emit for function tools (on_tool_end is their only source).
            emit_tool_requests=False,
            emit_tool_responses=True,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )

    run_kwargs: dict[str, Any] = {"hooks": hooks, "max_turns": max_turns}
    if run_config is not None:
        run_kwargs["run_config"] = run_config

    try:
        result = await Runner.run(starting_agent, input, **run_kwargs)
    finally:
        # If the runner terminated mid-tool (max-turns, cancellation, SDK error),
        # on_tool_end never fired for the in-flight call, leaving its span open.
        # Drain any leftovers so they don't orphan in the tracing backend.
        close_open_tool_spans = getattr(hooks, "close_open_tool_spans", None)
        if callable(close_open_tool_spans):
            await close_open_tool_spans()

    resolved_model = model
    if resolved_model is None:
        agent_model = getattr(starting_agent, "model", None)
        resolved_model = str(agent_model) if agent_model else None

    return OpenAIAgentsTurnResult(
        result=result,
        usage=_extract_turn_usage(result, model=resolved_model),
    )
