# [Agentic] Batch Events

## What You'll Learn

Demonstrates limitations of the base agentic protocol with concurrent event processing. When multiple events arrive rapidly, base agentic agents handle them sequentially, which can cause issues.

**Problem shown:** Race conditions and ordering issues when events arrive faster than the agent can process them.

## Quick Start

```bash
cd examples/tutorials/10_agentic/00_base/080_batch_events
uv run agentex agents run --manifest manifest.yaml
```

## Why This Matters

This tutorial shows **when you need Temporal**. If your agent needs to:
- Handle events that might arrive out of order
- Process multiple events in parallel safely
- Maintain consistent state under concurrent load

Then you should use Temporal workflows (see tutorials 10_agentic/10_temporal/) which provide:
- Deterministic event ordering
- Safe concurrent processing
- Guaranteed state consistency

This is the "breaking point" tutorial that motivates moving to Temporal for production agents.
