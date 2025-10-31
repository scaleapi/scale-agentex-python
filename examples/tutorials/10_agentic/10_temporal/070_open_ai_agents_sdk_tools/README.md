# [Temporal] OpenAI Agents SDK - Tools

**Part of the [OpenAI SDK + Temporal integration series](../README.md)** → Previous: [060 Hello World](../060_open_ai_agents_sdk_hello_world/)

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

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Temporal UI available at http://localhost:8233
- OpenAI Agents SDK plugin configured (see [060_hello_world](../060_open_ai_agents_sdk_hello_world/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/070_open_ai_agents_sdk_tools
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8233 to see tool calls as activities.

## Try It

### Pattern 1: Single Activity Tool

Ask "What's the weather in San Francisco?"

1. Check the agent response:

![Weather Response](../_images/weather_response.png)

2. Open Temporal UI (localhost:8233)
3. See a single `get_weather` activity created:

![Weather Activity](../_images/weather_activity_tool.png)

The activity shows the external call with retry capability. Each step (model invocation → tool call → model invocation) is durable.

### Pattern 2: Multi-Activity Tool (Optional)

To try the advanced banking example, uncomment the `move_money` sections in the code, then ask to move money.

1. Check the agent response:

![Money Transfer Response](../_images/move_money_response.png)

2. Open Temporal UI and see TWO sequential activities:

![Money Transfer Workflow](../_images/move_money_temporal.png)

- First: `withdraw_money` activity executes
- Then: `deposit_money` activity executes
- Each activity shows its parameters and execution time

**Critical insight:** If the system crashes after withdraw but before deposit, Temporal resumes exactly where it left off. The deposit will still happen - guaranteed transactional integrity.

## Key Code

### Pattern 1: Single Activity Tool
```python
# Define the activity
@activity.defn
async def get_weather(city: str) -> str:
    """Get the weather for a given city"""
    # This could be an API call - Temporal handles retries
    return f"The weather in {city} is sunny"

# Use activity_as_tool to convert it
weather_agent = Agent(
    name="Weather Assistant",
    instructions="Use the get_weather tool to answer weather questions.",
    tools=[
        activity_as_tool(get_weather, start_to_close_timeout=timedelta(seconds=10))
    ]
)
```

### Pattern 2: Multi-Activity Tool
```python
# Define individual activities
@activity.defn
async def withdraw_money(from_account: str, amount: float) -> str:
    # Simulate API call
    await asyncio.sleep(5)
    return f"Withdrew ${amount} from {from_account}"

@activity.defn
async def deposit_money(to_account: str, amount: float) -> str:
    # Simulate API call
    await asyncio.sleep(10)
    return f"Deposited ${amount} into {to_account}"

# Create a function tool that orchestrates both activities
@function_tool
async def move_money(from_account: str, to_account: str, amount: float) -> str:
    """Move money from one account to another"""

    # Step 1: Withdraw (becomes an activity)
    await workflow.start_activity(
        "withdraw_money",
        args=[from_account, amount],
        start_to_close_timeout=timedelta(days=1)
    )

    # Step 2: Deposit (becomes an activity)
    await workflow.start_activity(
        "deposit_money",
        args=[to_account, amount],
        start_to_close_timeout=timedelta(days=1)
    )

    return "Money transferred successfully"

# Use the tool in your agent
money_agent = Agent(
    name="Money Mover",
    instructions="Use move_money to transfer funds between accounts.",
    tools=[move_money]
)
```

## When to Use Each Pattern

### Use Pattern 1 when:
- Tool performs a single external operation (API call, DB query)
- Operation is already idempotent
- No sequencing guarantees needed

### Use Pattern 2 when:
- Tool requires multiple sequential operations
- Order must be guaranteed (withdraw THEN deposit)
- Operations need to be atomic from the agent's perspective
- You want transactional integrity across steps

## Why This Matters

**Without Temporal:** If you withdraw money but crash before depositing, you're stuck in a broken state. The money is gone from the source account with no way to recover.

**With Temporal (Pattern 2):**
- Guaranteed execution with exact resumption after failures
- If the system crashes after withdraw, Temporal resumes and completes deposit
- Each step is tracked and retried independently
- Full observability of the entire operation

**Key insight:** Pattern 2 moves sequencing control from the LLM (which might call tools in wrong order) to your deterministic code (which guarantees correct order). The LLM still decides *when* to call the tool, but your code controls *how* the operations execute.

This makes agents production-ready for:
- Financial transactions
- Order fulfillment workflows
- Multi-step API integrations
- Any operation where partial completion is dangerous

## When to Use

**Pattern 1 (activity_as_tool):**
- Single API calls
- Database queries
- External service integrations
- Operations that are naturally atomic

**Pattern 2 (Multi-activity tools):**
- Financial transactions requiring sequencing
- Multi-step operations with dependencies
- Operations where order matters critically
- Workflows needing guaranteed atomicity

**Next:** [080_open_ai_agents_sdk_human_in_the_loop](../080_open_ai_agents_sdk_human_in_the_loop/) - Add human approval workflows
