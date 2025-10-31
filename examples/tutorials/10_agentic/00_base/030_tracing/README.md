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
- Understanding of agentic agents (see [000_hello_acp](../000_hello_acp/))

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

## When to Use
- Debugging complex agent behaviors
- Performance optimization and bottleneck identification
- Production monitoring and observability
- Understanding execution flow in multi-step agents

## Why This Matters
Without tracing, debugging agents is like flying blind. Tracing gives you visibility into what your agent is doing, how long operations take, and where failures occur. It's essential for production agents and invaluable during development.

**Next:** [040_other_sdks](../040_other_sdks/) - Integrate any SDK or framework
