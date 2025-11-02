# [Temporal] Workflow Activities

**Part of the [OpenAI SDK + Temporal integration series](../README.md)** → Previous: [030 Human in the Loop](../030_open_ai_agents_sdk_human_in_the_loop/)

## What You'll Learn

How to use Temporal activities for **workflow orchestration** alongside the OpenAI Agents SDK.

**Key Pattern:**
- OpenAI Agents SDK handles LLM interactions (`Runner.run`)
- Temporal activities handle everything else (database, notifications, reports)

**Difference from Tutorial 020:**
- **Tutorial 020**: Activities AS agent tools (agent decides when to call)
- **Tutorial 040**: Activities FOR workflow logic (workflow decides when to call)

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Temporal UI available at http://localhost:8233
- OpenAI API key configured (see previous tutorials)
- Understanding of OpenAI Agents SDK (see [010](../010_open_ai_agents_sdk_hello_world/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/040_workflow_activities
export OPENAI_API_KEY="your-key-here"
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8233 to see workflow activities.

## Try It

1. Send a message to the agent (it responds normally)
2. Check Temporal UI - you'll see MULTIPLE activities:
   - `invoke_model_activity` (agent processing - from SDK plugin)
   - `save_to_database` (workflow saves conversation)
   - `send_notification` (workflow sends notification)
3. Send 3 messages total:
   - After message #3, see `process_batch` activity run
4. Check the agent responses - you'll see:
   - Normal agent responses
   - System messages about database saves
   - Email notifications
   - Batch processing updates

![Workflow Activities](../_images/workflow_activities.png)

## Key Code

### Activities for Workflow Orchestration

```python
# In activities.py - these are NOT agent tools

@activity.defn
async def save_to_database(task_id: str, data: dict) -> str:
    """Save conversation to database - workflow controls this"""
    # Make database call (PostgreSQL, MongoDB, etc.)
    return f"Saved {len(data)} fields to database"

@activity.defn
async def send_notification(task_id: str, message: str, channel: str) -> str:
    """Send notifications - workflow controls this"""
    # Call email API, Slack, Discord, etc.
    return f"Notification sent via {channel}"

@activity.defn
async def process_batch(task_id: str, items: list, batch_num: int) -> dict:
    """Process data in batches - workflow controls this"""
    # Batch processing, analytics, etc.
    return {"batch_number": batch_num, "items_processed": len(items)}
```

### Workflow Using Activities

```python
# In workflow.py - workflow calls activities directly

@workflow.signal(name=SignalName.RECEIVE_EVENT)
async def on_task_event_send(self, params: SendEventParams):
    # STEP 1: Agent processes message (OpenAI Agents SDK)
    result = await Runner.run(agent, self._state.input_list, hooks=hooks)

    # STEP 2: Save to database (Workflow Activity - NOT agent tool)
    await workflow.execute_activity(
        save_to_database,
        args=[task_id, conversation_data],
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(maximum_attempts=3)
    )

    # STEP 3: Send notification (Workflow Activity - NOT agent tool)
    await workflow.execute_activity(
        send_notification,
        args=[task_id, "Turn completed", "email"],
        start_to_close_timeout=timedelta(seconds=30)
    )

    # STEP 4: Batch processing every 3 messages (Workflow Logic)
    if self._state.turn_number % 3 == 0:
        await workflow.execute_activity(
            process_batch,
            args=[task_id, recent_messages, batch_num],
            start_to_close_timeout=timedelta(minutes=5)
        )
```

## When to Use Each Pattern

### Use Activities AS Agent Tools (Tutorial 020) when:
- Agent decides when to call the operation
- User explicitly requests the action ("check the weather")
- Operation is part of the agent's capabilities
- Agent needs the result to formulate a response

### Use Activities FOR Workflow Orchestration (Tutorial 040) when:
- Workflow orchestration logic (not agent decisions)
- Background operations (notifications, logging, metrics)
- Post-processing (saving results, generating reports)
- Infrastructure concerns (health checks, cleanup)
- Business rules that always apply (audit logs, database saves)

## Use Cases

**Workflow-Level Activities are perfect for:**
- **Database Operations**: Save every conversation to PostgreSQL
- **Notifications**: Email user after every agent response
- **Audit Logs**: Log all interactions for compliance
- **Batch Processing**: Aggregate data every N messages
- **Report Generation**: Create summary reports periodically
- **External Integrations**: Update CRM, trigger webhooks
- **Monitoring**: Send metrics to Datadog, New Relic
- **Cleanup**: Delete old data, archive conversations

## Why This Matters

**Not everything should go through the agent.** Some operations are:
- Infrastructure concerns (logging, monitoring)
- Business requirements (always save to DB, always send notification)
- Background operations (don't need agent awareness)

**Workflow-level activities provide:**
- ✅ Guaranteed execution (even if agent fails)
- ✅ Separate retry policies from agent operations
- ✅ Clear separation of concerns
- ✅ Better observability (separate activities in Temporal UI)
- ✅ Independent failure handling

**Example:** If saving to database fails, the workflow can retry the database activity without re-running the expensive LLM call.

## Architecture

```
User Message
     ↓
[Agent Processing]      ← OpenAI Agents SDK (invoke_model_activity)
     ↓
[Save to Database]      ← Workflow Activity (save_to_database)
     ↓
[Send Notification]     ← Workflow Activity (send_notification)
     ↓
[Batch Processing?]     ← Workflow Activity (process_batch) [conditional]
     ↓
Response to User
```

Each step is a separate durable activity with independent retry policies and observability.

## When to Use

- Production agents that need infrastructure operations
- Systems with regulatory requirements (audit logs, compliance)
- Applications with external integrations (CRM, email, Slack)
- Workflows with background processing needs
- Services requiring guaranteed side effects (database writes, notifications)

**Next:** (Coming soon) State Machines - Complex multi-phase workflows

---

**For detailed setup instructions, see the main [README](../README.md)**
