# Tutorial 120: Temporal OpenAI Agents SDK with a Local Sandbox

This tutorial demonstrates running an [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents)
`SandboxAgent` inside a **Temporal** workflow, backed by the **local**
(`unix_local`) sandbox.

The agent is a "local sandbox assistant": it answers questions by actually running
real shell commands (e.g. `python3 --version`, `ls`, `python3 -c "..."`) instead of
guessing. Because it runs inside Temporal, the sandbox tool calls become durable,
retried, and observable activities.

This mirrors the canonical OpenAI Agents SDK Temporal example
(`060_open_ai_agents_sdk_hello_world`) and the tools example
(`070_open_ai_agents_sdk_tools`). The new piece is the **Temporal sandbox bridge**.

## Key Concepts

### Temporal ACP
The Temporal ACP model (`acp_type: async`, `temporal.enabled: true`) maps task
lifecycle to a Temporal workflow:
- `@workflow.run` (`on_task_create`) keeps the conversation alive.
- `@workflow.signal(name=SignalName.RECEIVE_EVENT)` (`on_task_event_send`) handles
  each user message.

No ACP handlers are registered by hand — the `TemporalACPConfig` wires them to the
workflow automatically.

### Streaming (Interceptor + Model Provider + Hooks)
Real-time streaming uses STANDARD Temporal components — no forked plugin:
- **`ContextInterceptor`** threads `task_id` through activity headers. The workflow
  sets `self._task_id` so the interceptor can read it.
- **`TemporalStreamingModelProvider`** returns a model that streams tokens to Redis
  in real time while still returning the complete response to Temporal for
  determinism / replay safety.
- **`TemporalStreamingHooks`** creates the lifecycle messages (tool request /
  response, etc.) in the database.

The `stream_lifecycle_content` activity must be registered on the worker alongside
`get_all_activities()`.

### The Temporal sandbox bridge (`UnixLocalSandboxClient`)
The sandbox client is registered ON THE WORKER (and the ACP) via the standard
plugin:

```python
from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, SandboxClientProvider

OpenAIAgentsPlugin(
    model_provider=TemporalStreamingModelProvider(),
    sandbox_clients=[SandboxClientProvider("local", UnixLocalSandboxClient())],
)
```

Inside the workflow, the run is pointed at that backend by name:

```python
from temporalio.contrib.openai_agents.workflow import temporal_sandbox_client
from agents.sandbox import SandboxAgent, SandboxRunConfig
from agents.run_config import RunConfig
from agents.sandbox.snapshot import NoopSnapshotSpec
from agents.sandbox.capabilities import Shell
from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClientOptions

agent = SandboxAgent(
    name="Local Sandbox Assistant",
    model="gpt-4o-mini",
    instructions="...use the shell tools to actually run commands...",
    capabilities=[Shell()],
)
run_config = RunConfig(
    sandbox=SandboxRunConfig(
        client=temporal_sandbox_client("local"),
        options=UnixLocalSandboxClientOptions(),
        snapshot=NoopSnapshotSpec(),  # skip the per-turn workspace snapshot
    )
)
result = await Runner.run(
    agent, self._state.input_list, run_config=run_config,
    hooks=TemporalStreamingHooks(task_id=params.task.id),
)
```

`temporal_sandbox_client("local")` resolves the worker-registered client, so the
sandbox shell tool calls run as Temporal activities (durable + observable in the
Temporal UI).

## Two important lessons

1. **Don't double-post the assistant message.** The `TemporalStreamingModelProvider`
   already streams AND persists the assistant's response. If you also call
   `adk.messages.create(...)` after `Runner.run`, the answer shows up twice. We only
   persist conversation state for the next turn via `result.to_input_list()`.
2. **Use `NoopSnapshotSpec()`.** Without it, the sandbox tries to take a per-turn
   workspace snapshot, and stopping the sandbox can raise
   `WorkspaceArchiveReadError`. `NoopSnapshotSpec()` skips that snapshot.

## Files

| File | Description |
|------|-------------|
| `project/acp.py` | Temporal ACP server (plugin + sandbox client + interceptor) |
| `project/run_worker.py` | Temporal worker (registers workflow, activities, plugin, sandbox client) |
| `project/workflow.py` | `BaseWorkflow` that runs the `SandboxAgent` against the local sandbox |
| `tests/test_agent.py` | Integration tests (polling pattern) |
| `manifest.yaml` | Agent configuration (temporal enabled) |
| `environments.yaml` | Per-environment deployment overrides |

## Running Locally

```bash
# From this directory
agentex agents run
```

Set `OPENAI_API_KEY` (or `LITELLM_API_KEY` if you're behind the Scale LiteLLM
gateway) in your environment or in a `.env` file in `project/` so the agent can call
the model.

## Running Tests

```bash
pytest tests/test_agent.py -v
```

## Further Reading

- OpenAI Agents SDK guide: https://developers.openai.com/api/docs/guides/agents
- The async (non-Temporal) variant: `10_async/00_base/120_openai_agents_local_sandbox`
- The canonical OpenAI Agents SDK Temporal example: `10_async/10_temporal/060_open_ai_agents_sdk_hello_world`
