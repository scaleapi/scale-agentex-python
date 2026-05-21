# Tutorial 110 (temporal): Pydantic AI Agent

This tutorial demonstrates a **durable** Pydantic AI agent on AgentEx, backed by Temporal:
- Workflow state survives crashes mid-conversation (Temporal replay)
- Every LLM call and every tool call becomes its own Temporal activity (independent retries + observability)
- Streaming via Redis still works — token-by-token deltas appear in the UI in real time

This is the Temporal counterpart to the async base tutorial at [`10_async/00_base/110_pydantic_ai/`](../../00_base/110_pydantic_ai/).

## Why Temporal? Why not just async?

In async base 110, the agent state lives in memory inside the ACP process. If that process dies mid-LLM-call, the in-flight turn is lost. Temporal fixes this by:

1. Recording every external interaction (LLM call, tool call) to a durable event log.
2. On worker restart, **replaying** the workflow code, using cached activity results to skip work that already finished.
3. Letting workflows live forever — multi-day conversations or human-in-the-loop flows just work.

## Architecture at a glance

Two long-running processes plus shared infrastructure:

```
┌──────────────────────────┐        ┌──────────────────────────┐
│ uvicorn project.acp:acp  │        │ python -m run_worker     │
│  (HTTP shim, forwards    │        │  (executes workflows +   │
│   signals to Temporal)   │        │   activities)            │
└──────────────────────────┘        └──────────────────────────┘
              │                                  │
              └────► Temporal server ◄───────────┘
                     (event log + queue)

                   Redis ◄─── activities push deltas
                     │
                     └─── Agentex API tails ──► UI client
```

The HTTP server is a thin shim that translates `task/event/send` into Temporal signals. The worker is where your agent code actually runs. Temporal sits in between, recording everything.

## Key code patterns

### `project/agent.py` — wrap the base agent in `TemporalAgent`

```python
base_agent = Agent(MODEL_NAME, deps_type=TaskDeps, system_prompt=...)
base_agent.tool_plain(get_weather)

temporal_agent = TemporalAgent(
    base_agent,
    name="at110_pydantic_ai_agent",
    event_stream_handler=event_handler,  # streams to Redis from inside the model activity
)
```

`TemporalAgent` (from `pydantic_ai.durable_exec.temporal`) wraps a normal Pydantic AI Agent so that:
- Each LLM call runs in its own activity
- Each tool call runs in its own activity
- The wrapping is invisible to the workflow code that calls `temporal_agent.run(...)`

### `project/workflow.py` — declare `__pydantic_ai_agents__`

```python
@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At110PydanticAiWorkflow(BaseWorkflow):
    __pydantic_ai_agents__ = [temporal_agent]   # ← discovered by PydanticAIPlugin

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params):
        await adk.messages.create(task_id=params.task.id, content=params.event.content)
        result = await temporal_agent.run(
            params.event.content.content,
            deps=TaskDeps(task_id=params.task.id),
        )
```

The `__pydantic_ai_agents__` attribute is how `PydanticAIPlugin` discovers which activities to register on the worker — no manual activity list needed.

### `project/acp.py` — no handlers, just plugin wiring

```python
acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[PydanticAIPlugin()],
    ),
)
```

When `type="temporal"`, FastACP auto-wires HTTP → workflow signals. You don't define `@acp.on_task_event_send` anywhere — Temporal handles it.

### `project/run_worker.py` — boot the worker with the plugin

```python
worker = AgentexWorker(
    task_queue=task_queue_name,
    plugins=[PydanticAIPlugin()],
)
await worker.run(
    activities=get_all_activities(),
    workflow=At110PydanticAiWorkflow,
)
```

`get_all_activities()` returns the built-in Agentex activities (state, messages, streaming, tracing). Pydantic AI's per-agent activities are auto-added by the plugin.

## Files

| File | Purpose |
|------|---------|
| `project/acp.py` | Thin HTTP shim — `FastACP.create(type="temporal", ...)` |
| `project/workflow.py` | `@workflow.defn` class with the signal handler |
| `project/agent.py` | Base Pydantic AI Agent wrapped in `TemporalAgent` |
| `project/tools.py` | Tool functions (must be `async` for Temporal compatibility) |
| `project/run_worker.py` | Worker boot script (separate process) |
| `tests/test_agent.py` | End-to-end test verifying tool round-trips |
| `manifest.yaml` | Sets `temporal.enabled: true` and declares workflow + queue name |

## Running Locally

You'll need three terminals open (this is the price of Temporal):

```bash
# Terminal 1 — backend services (separate repo)
cd ~/scale-agentex/agentex
make dev   # brings up Temporal, Redis, Postgres, Agentex API

# Terminal 2 — this tutorial (ACP server + Temporal worker)
cd ~/scale-agentex-python/examples/tutorials/10_async/10_temporal/110_pydantic_ai
agentex agents run   # this also launches the worker process

# Terminal 3 — tests
cd ~/scale-agentex-python/examples/tutorials/10_async/10_temporal/110_pydantic_ai
uv run pytest tests/test_agent.py -v
```

Watch the Temporal UI at http://localhost:8233 — you'll see workflow executions, signal events, and one activity per LLM call + one per tool call.

## Sync vs Async vs Temporal — How the code differs

| Concern | Sync (040) | Async base (110) | Temporal (this one) |
|---|---|---|---|
| `project/acp.py` | `@acp.on_message_send` yields events | `@acp.on_task_event_send` pushes to Redis | **No handlers** — `FastACP.create(type="temporal", ...)` |
| Where the agent runs | In the ACP HTTP process | In the ACP HTTP process | In a separate worker process |
| Durability | Ephemeral — request-scoped | Ephemeral — process-scoped | **Durable** — survives worker restarts via Temporal replay |
| Per-call retries | None | None | Each model + tool call automatically retried by Temporal |
| Code we add | — | `acp.py` handler | `workflow.py`, `run_worker.py`, wrap agent in `TemporalAgent` |

## Notes

- Multi-turn conversation memory is not wired here. Workflow state (`self._turn_number`) is durable, but message history isn't currently threaded into `temporal_agent.run(..., message_history=...)`. To add: load via `adk.messages.list(task_id=...)` inside the signal handler and pass through.
- Reasoning/thinking tokens are not exercised by `gpt-4o-mini`. Swap to a reasoning-capable model to exercise that branch end-to-end.
- Tools must be `async` (Pydantic AI's Temporal integration requires it — sync tools would run in threads, breaking Temporal's determinism guarantees).
