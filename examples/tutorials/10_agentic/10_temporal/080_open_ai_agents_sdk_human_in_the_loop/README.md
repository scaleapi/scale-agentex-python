# [Temporal] OpenAI Agents SDK - Human in the Loop

**Part of the [OpenAI SDK + Temporal integration series](../README.md)** → Previous: [070 Tools](../070_open_ai_agents_sdk_tools/)

## What You'll Learn

How to pause agent execution and wait indefinitely for human approval using Temporal's child workflows and signals. The agent can wait for hours, days, or weeks for human input without consuming resources - and if the system crashes, it resumes exactly where it left off.

**Pattern:**
1. Agent calls `wait_for_confirmation` tool
2. Tool spawns a child workflow that waits for a signal
3. Human approves/rejects via Temporal CLI or web UI
4. Child workflow completes, agent continues with the response

## New Temporal Concepts

### Signals
Signals are a way for external systems to interact with running workflows. Think of them as secure, durable messages sent to your workflow from the outside world.

**Use cases:**
- User approving/rejecting an action in a web app
- Payment confirmation triggering shipping
- Live data feeds (stock prices) triggering trades
- Webhooks from external services updating workflow state

**How it works:** Define a function in your workflow class with the `@workflow.signal` decorator. External systems can then send signals using:
- Temporal SDK (by workflow ID)
- Another Temporal workflow
- Temporal CLI
- Temporal Web UI

[Learn more about signals](https://docs.temporal.io/develop/python/message-passing#send-signal-from-client)

### Child Workflows
Child workflows are like spawning a new workflow from within your current workflow. Similar to calling a function in traditional programming, but the child workflow:
- Runs independently with its own execution history
- Inherits all Temporal durability guarantees
- Can be monitored separately in Temporal UI
- Continues running even if the parent has issues

**Why use child workflows for human-in-the-loop?**
- The parent workflow can continue processing while waiting
- The child workflow can wait indefinitely for human input
- Full isolation between waiting logic and main agent logic
- Clean separation of concerns

[Learn more about child workflows](https://docs.temporal.io/develop/python/child-workflows)

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Temporal UI available at http://localhost:8233
- OpenAI Agents SDK plugin configured (see [060_hello_world](../060_open_ai_agents_sdk_hello_world/))
- Understanding of tools (see [070_tools](../070_open_ai_agents_sdk_tools/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/080_open_ai_agents_sdk_human_in_the_loop
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8233 to see child workflows and signals.

## Try It

1. Ask the agent to do something that requires approval (e.g., "Order 100 widgets")
2. The agent will call `wait_for_confirmation` and pause
3. Open Temporal UI (localhost:8233)
4. Find the parent workflow - you'll see it's waiting on the child workflow:

![Parent Workflow Waiting](../_images/human_in_the_loop_workflow.png)

5. Find the child workflow - it's waiting for a signal:

![Child Workflow Waiting](../_images/human_in_the_loop_child_workflow.png)

6. Send approval signal via CLI:

```bash
temporal workflow signal \
  --workflow-id="<child-workflow-id>" \
  --name="fulfill_order_signal" \
  --input=true
```

7. Watch both workflows complete - the agent resumes and finishes the action

## Key Code

### The Tool: Spawning a Child Workflow
```python
from agents import function_tool
from temporalio import workflow
from project.child_workflow import ChildWorkflow
from temporalio.workflow import ParentClosePolicy

@function_tool
async def wait_for_confirmation(confirmation: bool) -> str:
    """Wait for human confirmation before proceeding"""

    # Spawn a child workflow that will wait for a signal
    result = await workflow.execute_child_workflow(
        ChildWorkflow.on_task_create,
        environment_variables.WORKFLOW_NAME + "_child",
        id="child-workflow-id",
        parent_close_policy=ParentClosePolicy.TERMINATE,
    )

    return result
```

### The Child Workflow: Waiting for Signals
```python
import asyncio
from temporalio import workflow

@workflow.defn(name=environment_variables.WORKFLOW_NAME + "_child")
class ChildWorkflow():
    def __init__(self):
        # Queue to hold signals
        self._pending_confirmation: asyncio.Queue[bool] = asyncio.Queue()

    @workflow.run
    async def on_task_create(self, name: str) -> str:
        logger.info(f"Child workflow started: {name}")

        # Wait indefinitely until we receive a signal
        await workflow.wait_condition(
            lambda: not self._pending_confirmation.empty()
        )

        # Signal received - complete the workflow
        return "Task completed"

    @workflow.signal
    async def fulfill_order_signal(self, success: bool) -> None:
        """External systems call this to approve/reject"""
        if success:
            await self._pending_confirmation.put(True)
```

### Using the Tool in Your Agent
```python
confirm_order_agent = Agent(
    name="Confirm Order",
    instructions="When user asks to confirm an order, use wait_for_confirmation tool.",
    tools=[wait_for_confirmation]
)

result = await Runner.run(confirm_order_agent, params.event.content.content)
```

## How It Works

1. **Agent calls tool**: The LLM decides to call `wait_for_confirmation`
2. **Child workflow spawned**: A new workflow is created with its own ID
3. **Child waits**: Uses `workflow.wait_condition()` to block until signal arrives
4. **Parent waits**: Parent workflow is blocked waiting for child to complete
5. **Signal sent**: External system (CLI, web app, API) sends signal with workflow ID
6. **Signal received**: Child workflow's `fulfill_order_signal()` method is called
7. **Queue updated**: Signal handler adds item to queue
8. **Wait condition satisfied**: `wait_condition()` unblocks
9. **Child completes**: Returns result to parent
10. **Parent resumes**: Agent continues with the response

**Critical insight:** At any point, if the system crashes:
- Both workflows are durable and will resume
- No context is lost
- The moment the signal arrives, execution continues

## Why This Matters

**Without Temporal:** If your system crashes while waiting for human approval, you lose all context about what was being approved. The user has to start over.

**With Temporal:**
- The workflow waits durably (hours, days, weeks)
- If the system crashes and restarts, context is preserved
- The moment a human sends approval, workflow resumes exactly where it left off
- Full audit trail of who approved what and when

**Production use cases:**
- **Financial transactions**: Agent initiates transfer, human approves
- **Legal document processing**: AI extracts data, lawyer reviews
- **Multi-step purchasing**: Agent negotiates, manager approves
- **Compliance workflows**: System flags issue, human decides action
- **High-stakes decisions**: Any operation requiring human judgment

This pattern transforms agents from fully automated systems into **collaborative AI assistants** that know when to ask for help.

## When to Use
- Financial transactions requiring approval
- High-stakes decisions needing human judgment
- Compliance workflows with mandatory review steps
- Legal or contractual operations
- Any operation where errors have serious consequences
- Workflows where AI assists but humans decide

**Congratulations!** You've completed all AgentEx tutorials. You now know how to build production-ready agents from simple sync patterns to complex durable workflows with human oversight.
