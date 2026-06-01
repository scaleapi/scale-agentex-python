# Tutorial 120: Async OpenAI Agents SDK with a Local Sandbox

This tutorial demonstrates how to build an **async (non-Temporal)** agent on AgentEx
using the [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents)
and its **sandbox** runtime, running with the **local** (`unix_local`) backend.

The agent is a "local sandbox assistant": it answers questions by actually running
real shell commands (e.g. `python3 --version`, `ls /tmp`, `python3 -c "..."`)
instead of guessing.

This mirrors the Pydantic AI async tutorial (`110_pydantic_ai`): same async ACP
model (`acp_type: async`, `temporal.enabled: false`), same per-task `adk.state`
multi-turn memory pattern. The difference is the runtime — here we use the OpenAI
Agents SDK `SandboxAgent` with the local sandbox backend.

## Key Concepts

### Async ACP (base)
The async ACP model is event-driven: `on_task_create` initializes per-task state,
and `on_task_event_send` handles each user message. Conversation history is
persisted across turns via `adk.state`.

### OpenAI Agents SDK Sandbox
The OpenAI Agents SDK ships `agents.sandbox`, which lets you give an agent
**capabilities** (instead of hand-written tools) that the runtime turns into real
tools backed by a sandbox:

- **`SandboxAgent`**: an `Agent` that is granted sandbox capabilities.
- **Capabilities** (`from agents.sandbox.capabilities import Shell, Filesystem, Memory`):
  each capability expands into a set of real tools. This tutorial uses `Shell`, which
  lets the model run real shell commands.
- **`SandboxRunConfig`** + a sandbox **client**: tells the runtime *where* the tools
  actually execute.

### The LOCAL sandbox (`UnixLocalSandboxClient`)
This tutorial uses the local backend
(`from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient, UnixLocalSandboxClientOptions`),
`backend_id="unix_local"`. The local sandbox runs shell commands **ON THE HOST** —
the agent's own container/process. There is **no Docker, no Temporal, and no remote
sandbox infrastructure** involved.

The sandbox is wired up through the SDK's `RunConfig`:

```python
from agents import Runner, set_tracing_disabled
from agents.run_config import RunConfig
from agents.sandbox import SandboxAgent, SandboxRunConfig
from agents.sandbox.capabilities import Shell
from agents.sandbox.sandboxes.unix_local import (
    UnixLocalSandboxClient,
    UnixLocalSandboxClientOptions,
)

set_tracing_disabled(True)  # avoid api.openai.com tracing 401 behind a gateway

agent = SandboxAgent(
    name="Local Sandbox Assistant",
    instructions="...use the shell tools to actually run commands...",
    capabilities=[Shell()],
)
run_config = RunConfig(
    sandbox=SandboxRunConfig(
        client=UnixLocalSandboxClient(),
        options=UnixLocalSandboxClientOptions(),
    )
)
result = await Runner.run(agent, input=input_list, run_config=run_config)
print(result.final_output)
```

`Runner.run` drives the full tool-call loop internally: the model issues shell
commands, the local sandbox runs them on the host, the output is fed back, and the
loop continues until the model produces a final answer. Because the loop is
self-contained, the async handler runs the agent and persists a single final
`TextContent` rather than streaming tokens.

## Files

| File | Description |
|------|-------------|
| `project/acp.py` | Async ACP server + handlers (`adk.state` multi-turn, runs the sandbox agent) |
| `project/agent.py` | `SandboxAgent` + `RunConfig(sandbox=...)` wiring + `run_agent` |
| `project/tools.py` | Sandbox capability factory (`Shell`) |
| `tests/test_agent.py` | Integration tests (polling pattern) |
| `manifest.yaml` | Agent configuration |

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

## Notes

- **No infra required.** Because this uses the `unix_local` backend, the shell tools
  run directly in the agent's process — no Docker daemon, no Temporal, no remote
  sandbox. Swap the client for a remote/containerized backend to isolate execution.
- **Tracing.** `set_tracing_disabled(True)` turns off the OpenAI Agents SDK's native
  tracer (which would otherwise try to ship traces to `api.openai.com`). The manifest
  also sets `OPENAI_AGENTS_DISABLE_TRACING=1`. AgentEx/SGP tracing still runs via the
  tracing manager configured in `acp.py` when SGP credentials are present.
- **Capabilities are the tools.** To let the agent do more, add capabilities in
  `project/tools.py` (e.g. `Filesystem()`, `Memory()`).

## Further Reading

- OpenAI Agents SDK guide: https://developers.openai.com/api/docs/guides/agents
- The Temporal variant of this tutorial: `10_async/10_temporal/120_openai_agents_local_sandbox`
