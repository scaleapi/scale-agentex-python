# [Agentic] Batch Events

Demonstrates limitations of the base agentic protocol with concurrent event processing. When multiple events arrive rapidly, base agentic agents handle them sequentially, which can cause issues.

## What You'll Learn
- Limitations of non-Temporal agentic agents
- Race conditions and ordering issues in concurrent scenarios
- When you need workflow orchestration
- Why this motivates Temporal adoption

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Understanding of agentic patterns (see previous tutorials)

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

## When to Use (This Pattern)
This tutorial shows what NOT to use for production. Use base agentic agents only when:
- Events are infrequent (< 1 per second)
- Order doesn't matter
- State consistency isn't critical

## Why This Matters
Every production agent eventually hits concurrency issues. This tutorial shows you those limits early, so you know when to graduate to Temporal. Better to learn this lesson in a tutorial than in production!

**Next:** Ready for production? → [../10_temporal/000_hello_acp](../../10_temporal/000_hello_acp/) or explore [090_multi_agent_non_temporal](../090_multi_agent_non_temporal/) for complex non-Temporal coordination
