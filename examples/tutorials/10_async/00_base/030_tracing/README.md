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

## Failure-Check Attributes

Offline failure checks read attributes the agent declares on its spans. Build them from one
spec instead of hand-writing keys. The spec validates its values on construction, and each
attribute lands in span metadata as a flat `sgp.agent.*` key holding a native JSON value (a
list stays a list and a step budget stays an integer). The output schema is the exception and
is written as a JSON string, because the span store would spread a schema object into many paths.

```python
import dataclasses

spec = adk.FailureCheckSpec(
    required_outputs=["answer"],
    step_budget=20,
    verification=[adk.VerificationRule(step="check_answer", verifies="answer")],
    escalation_channels=["send_email.to"],
    prompt_version="2026-10-26",
)
async with adk.tracing.span(trace_id=task.id, name="agent", data=spec.attributes()) as root:
    ...
    # The stop reason is only known at the end.
    done = dataclasses.replace(spec, stop_reason="completed")
    if root:
        root.data = {**(root.data or {}), **done.attributes()}
```

A span that produces a required output, runs a verification or escalates one carries a single
attribute, passed as its `data`: `adk.failure_attributes.output_name("answer")`,
`verification_result("pass")` (or `"fail"`) and `escalates(verify_span.id)`, which takes several
span ids when one escalation covers several failures. The span
`adk.tracing.span` yields is `None` when `trace_id` is empty or the span fails to start, so
guard it before reading `.data` or `.id`.

An OpenTelemetry producer passes any of these dicts through `failure_attributes.otel_attributes`
before setting them on a span, and names an OpenTelemetry span to `escalates` as
`failure_attributes.otel_span_id(span)`.

The SGP export adds `__agent_version__` when `AGENT_VERSION` is set, and `__commit_sha__` when the
process starts with `AGENT_COMMIT_SHA` set to a valid git SHA, so only `prompt_version` is yours to
declare.

## When to Use
- Debugging complex agent behaviors
- Performance optimization and bottleneck identification
- Production monitoring and observability
- Understanding execution flow in multi-step agents

## Why This Matters
Without tracing, debugging agents is like flying blind. Tracing gives you visibility into what your agent is doing, how long operations take, and where failures occur. It's essential for production agents and invaluable during development.

**Next:** [040_other_sdks](../040_other_sdks/) - Integrate any SDK or framework
