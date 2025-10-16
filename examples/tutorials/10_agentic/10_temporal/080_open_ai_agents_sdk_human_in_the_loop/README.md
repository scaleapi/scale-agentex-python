# [Temporal] OpenAI Agents SDK - Human in the Loop

## What You'll Learn

How to pause agent execution and wait indefinitely for human approval using Temporal's child workflows and signals. The agent can wait for hours, days, or weeks for human input without consuming resources - and if the system crashes, it resumes exactly where it left off.

**Pattern:**
1. Agent calls `wait_for_confirmation` tool
2. Tool spawns a child workflow that waits for a signal
3. Human approves/rejects via Temporal CLI or web UI
4. Child workflow completes, agent continues with the response

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/080_open_ai_agents_sdk_human_in_the_loop
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8080 to see child workflows and signals.

## Try It

1. Ask the agent to do something that requires approval (e.g., "Order 100 widgets")
2. The agent will call `wait_for_confirmation` and pause
3. Open Temporal UI (localhost:8080) and find the child workflow ID
4. Send approval signal via CLI:

```bash
temporal workflow signal \
  --workflow-id="<child-workflow-id>" \
  --name="fulfill_order_signal" \
  --input=true
```

5. The agent resumes and completes the action

## Key Code

```python
# Tool that spawns child workflow for human approval
@function_tool
async def wait_for_confirmation(request: str) -> str:
    child_workflow_id = f"approval-{workflow.uuid4()}"

    # Spawn child workflow that waits for signal
    await workflow.start_child_workflow(
        ConfirmationWorkflow.run,
        id=child_workflow_id,
    )

    # Wait for human to send signal
    approved = await workflow.wait_condition(...)
    return "Approved!" if approved else "Rejected"
```

## Why This Matters

**Without Temporal:** If your system crashes while waiting for human approval, you lose all context about what was being approved. The user has to start over.

**With Temporal:** The workflow waits durably. If the system crashes and restarts days later, the moment a human sends approval, the workflow resumes exactly where it left off with full context.

This enables real production patterns like:
- Financial transaction approvals
- Legal document reviews
- Multi-step purchasing workflows
- Any operation requiring human judgment in the loop
