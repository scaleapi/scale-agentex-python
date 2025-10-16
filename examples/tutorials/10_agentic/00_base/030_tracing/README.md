# [Agentic] Tracing

## What You'll Learn

Add observability to your agents with spans and traces using `adk.tracing.start_span()`. Track execution flow, measure performance, and debug complex agent behaviors.

**Use case:** Understanding agent behavior, debugging issues, monitoring performance in production.

## Quick Start

```bash
cd examples/tutorials/10_agentic/00_base/030_tracing
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
