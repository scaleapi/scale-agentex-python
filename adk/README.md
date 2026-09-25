# agentex-sdk

The Agent Development Kit (ADK) overlay for the Agentex API.

## What's in here

This package ships everything under `agentex.lib.*`:

- **ACP server** (`agentex.lib.sdk.fastacp`) — FastAPI-based agent control plane.
- **Temporal workflows** (`agentex.lib.core.temporal`) — durable agent execution.
- **CLI** (`agentex.lib.cli`) — `agentex init`, `agentex run`, deploy helpers.
- **LLM provider integrations** (`agentex.lib.adk.providers`, `agentex.lib.core.temporal.plugins`) — OpenAI Agents, Claude Agent SDK, pydantic-ai, langgraph, litellm.
- **Observability** (`agentex.lib.core.tracing`, `agentex.lib.core.observability`) — SGP, Datadog, OpenTelemetry tracing processors.

## Installation

```sh
pip install agentex-sdk
```

This automatically pulls in [`agentex-client`](../) (the slim Stainless-generated REST client) so `from agentex import Agentex, AsyncAgentex` works the same as before.

## When to use this vs `agentex-client`

- **`agentex-sdk`** — you're authoring agents. Pulls everything: ACP server, Temporal, MCP, LLM providers, observability, CLI. ~37 deps.
- **`agentex-client`** — you only need to call the Agentex REST API. No agent authoring, no Temporal workflows, no FastACP server, no provider integrations. 6 deps.

The two packages contribute disjoint files to the `agentex.*` namespace — `agentex/lib/*` ships only from `agentex-sdk`.

## Workflow logging

Use the workflow logger in Temporal workflow code:

```python
from agentex.lib.core.temporal.logging import make_workflow_logger

logger = make_workflow_logger(__name__)
```

It suppresses logs while Temporal replays recorded history and adds top-level
`workflow_id` and `run_id` fields during workflow execution. It preserves the
message, caller fields, and exception details. Outside workflows, including in
activities, it behaves like the ordinary SDK logger.

New Temporal templates use this helper. Existing agents must replace their own
workflow loggers to get the same behavior. This does not create trace context or
add trace IDs to workflows that lack it. Temporal's worker diagnostics still report
replay failures.

## Repo layout

This package is hand-authored and lives at `adk/` inside [scaleapi/scale-agentex-python](https://github.com/scaleapi/scale-agentex-python). Stainless codegen never touches `adk/**` — it's outside the generated surface. The sibling `agentex-client` package lives at the repo root and IS Stainless-generated.

The wheel source is assembled from `src/agentex/lib/**` by `adk/hatch_build.py`.
