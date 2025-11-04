# [Temporal] Custom Activities

Learn how to extend Temporal workflows with custom activities for external operations like API calls, database queries, or complex computations.

## What You'll Learn
- How to define custom Temporal activities
- When to use activities vs inline workflow code
- Activity retry and timeout configuration
- Integrating external services into workflows

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Temporal UI available at http://localhost:8233
- Understanding of basic Temporal workflows (see [000_hello_acp](../000_hello_acp/))

## Quick Start

**Terminal 1 - Start Worker:**
```bash
cd examples/tutorials/10_agentic/10_temporal/030_custom_activities
uv run python project/run_worker.py
```

**Terminal 2 - Run Agent:**
```bash
uv run agentex agents run --manifest manifest.yaml
```

**Terminal 3 - Test via Notebook:**
```bash
jupyter notebook dev.ipynb
```

## Key Concepts

### Activities vs Workflow Code

**Use activities for:**
- External API calls
- Database operations
- File I/O or network operations
- Non-deterministic operations (random, time, external state)

**Use workflow code for:**
- Orchestration logic
- State management
- Decision making based on activity results

### Defining a Custom Activity

```python
# In project/activities.py
from temporalio import activity

@activity.defn
async def call_external_api(endpoint: str, data: dict) -> dict:
    """Activities can perform non-deterministic operations."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=data)
        return response.json()
```

### Using Activities in Workflows

```python
# In project/workflow.py
from temporalio import workflow

@workflow.defn
class MyWorkflow(BaseWorkflow):
    @workflow.run
    async def run(self, input: dict):
        # Activities are executed with retry and timeout policies
        result = await workflow.execute_activity(
            call_external_api,
            args=["https://api.example.com", input],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        return result
```

## Try It

1. Modify `project/activities.py` to add a new activity
2. Update `project/workflow.py` to call your activity
3. Register the activity in `project/run_worker.py`
4. Restart the worker and test via the notebook
5. Check Temporal UI at http://localhost:8233 to see activity execution and retries

## When to Use
- Integrating external services (OpenAI, databases, APIs)
- Operations that may fail and need automatic retries
- Long-running computations that should be checkpointed
- Separating business logic from orchestration

## Why This Matters
Activities are Temporal's way of handling the real world's messiness: network failures, API rate limits, and transient errors. They provide automatic retries, timeouts, and observability for operations that would otherwise require extensive error handling code.

---

**For detailed setup instructions, see [TEMPLATE_GUIDE.md](./TEMPLATE_GUIDE.md)**

**Next:** [050_agent_chat_guardrails](../050_agent_chat_guardrails/) - Add safety and validation to your workflows
