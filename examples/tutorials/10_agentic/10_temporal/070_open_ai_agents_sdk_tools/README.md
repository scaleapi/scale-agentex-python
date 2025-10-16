# [Temporal] OpenAI Agents SDK - Tools

## What You'll Learn

Two patterns for making agent tools durable with Temporal:

**Pattern 1: `activity_as_tool()`** - Single activity per tool call
- Use for: Single API calls, DB queries, external operations
- Example: `get_weather` tool → creates one `get_weather` activity
- 1:1 mapping between tool calls and activities

**Pattern 2: Function tools with multiple activities** - Multiple activities per tool call
- Use for: Multi-step operations needing guaranteed sequencing
- Example: `move_money` tool → creates `withdraw_money` activity THEN `deposit_money` activity
- 1:many mapping - your code controls execution order, not the LLM
- Ensures atomic operations (withdraw always happens before deposit)

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/070_open_ai_agents_sdk_tools
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8080 to see tool calls as activities.

## Try It

**Pattern 1 (implemented):** Ask "What's the weather in San Francisco?"
- Open Temporal UI (localhost:8080)
- See a single `get_weather` activity created
- The activity shows the external call with retry capability

**Pattern 2 (commented out in code):** Uncomment the `move_money` section, then ask to move money
- See TWO sequential activities: `withdraw_money` → `deposit_money`
- If the system crashes after withdraw but before deposit, Temporal resumes exactly where it left off
- The deposit will still happen - guaranteed transactional integrity

## Key Code

```python
# Pattern 1: Direct activity conversion
weather_agent = Agent(
    tools=[
        activity_as_tool(get_weather, start_to_close_timeout=timedelta(seconds=10))
    ]
)

# Pattern 2: Function tool coordinating multiple activities (see code for full example)
# The tool internally calls workflow.start_activity_method() multiple times
# guaranteeing the sequence and making each step durable
```

## Why This Matters

**Without Temporal:** If you withdraw money but crash before depositing, you're stuck in a broken state. The money is gone from the source account with no way to recover.

**With Temporal:** Guaranteed execution with exact resumption after failures. Either both operations complete, or the workflow can handle partial completion. This is what makes agents production-ready for real-world operations like financial transactions, order fulfillment, or any multi-step process.

**Key insight:** Pattern 2 moves sequencing control from the LLM (which might call tools in wrong order) to your deterministic code (which guarantees correct order).
