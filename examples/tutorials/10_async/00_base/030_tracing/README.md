# [Agentic] Tracing

Add observability to your agents with spans and traces using `adk.tracing.start_span()`. Track execution flow, measure performance, and debug complex agent behaviors.

## What You'll Learn
- How to instrument agents with tracing
- Creating hierarchical spans to track operations
- Viewing traces in Scale Groundplane
- Performance debugging with observability

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Understanding of async agents (see [000_hello_acp](../000_hello_acp/))

## Quick Start

```bash
cd examples/tutorials/10_async/00_base/030_tracing
uv run agentex agents run --manifest manifest.yaml
```

## Key Pattern

```python
# Start a span to track an operation
span = await adk.tracing.start_span(
    trace_id=task.id,
    name="LLM Call",
    input={"prompt": prompt}
)

# Do work...

# End span with output
await adk.tracing.end_span(
    span_id=span.id,
    output={"response": response}
)
```

Spans create a hierarchical view of agent execution, making it easy to see which operations take time and where errors occur.

## Token Usage & Cost Tracking

Token usage on spans is what the backend bills from, and it reads two shapes:

- **Per-turn aggregate** — `span.data["usage"]` + `span.data["cost_usd"]`. Emit at most
  once per turn, holding that turn's own usage (not a session-cumulative total). When a
  trace has an aggregate, the backend keeps it and de-dups all per-call spans against it.
- **Per-call detail** — `span.output["usage"]`. Optional; the SDK's LLM adapters
  (litellm, OpenAI Agents SDK, LangGraph) emit this automatically. Summed only when no
  aggregate exists in the trace.

Record the turn rollup with `adk.tracing.turn_span()` instead of hand-writing usage keys.
It accepts the harness `TurnUsage` that every turn adapter reports (`LangGraphTurn.usage()`,
`run_turn(...).usage`, `ClaudeCodeTurn.usage()`, ...), cost included:

```python
async with adk.tracing.turn_span(
    trace_id=task.id,
    name="turn",
    input={"prompt": prompt},
    task_id=task.id,
) as turn:
    result = await run_turn(...)
    turn.output = {"response": result.final_output}
    turn.record_usage(result.usage)  # TurnUsage; cost_usd stamped automatically
```

**Never put usage on both a rollup span's `output` and its per-call children's
`output`** — that double-counts. `turn_span` writes the aggregate to `data`, so child
spans stay safe to emit. Recognized token keys: `input_tokens`/`prompt_tokens`,
`output_tokens`/`completion_tokens`, `cached_input_tokens`/`cached_tokens`,
`reasoning_tokens`; cost is `cost_usd`.

## When to Use
- Debugging complex agent behaviors
- Performance optimization and bottleneck identification
- Production monitoring and observability
- Understanding execution flow in multi-step agents

## Why This Matters
Without tracing, debugging agents is like flying blind. Tracing gives you visibility into what your agent is doing, how long operations take, and where failures occur. It's essential for production agents and invaluable during development.

**Next:** [040_other_sdks](../040_other_sdks/) - Integrate any SDK or framework
