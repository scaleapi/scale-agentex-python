# at130-langgraph — AgentEx Temporal + LangGraph

A minimal Temporal-backed [LangGraph](https://langchain-ai.github.io/langgraph/)
agent. It uses the official [`temporalio.contrib.langgraph`](https://docs.temporal.io/develop/python/integrations/langgraph)
plugin so each LangGraph node runs as a durable **Temporal activity** (the LLM
`agent` node) or inline in the **workflow** (the `tools` node) — set per node
with `execute_in`. *Temporal is the runtime; LangGraph is the agent framework.*

> The Temporal LangGraph plugin is currently **experimental**.

## The graph

```
START → agent → (tool calls?) → tools → agent
             → (no tool calls?) → END
```

- `agent` (`execute_in="activity"`): the LLM call — a retried, observable Temporal activity.
- `tools` (`execute_in="workflow"`): runs the tool calls inline in the workflow.

The router and tools are `async` so LangGraph awaits them directly (a sync
callable is offloaded via `run_in_executor`, which Temporal workflows forbid).

## Project structure

```
130_langgraph/
├── project/
│   ├── acp.py          # Thin async ACP server; registers the LangGraphPlugin
│   ├── workflow.py     # Runs the graph each turn; keeps multi-turn memory
│   ├── graph.py        # LangGraph graph; nodes tagged execute_in activity/workflow
│   └── tools.py        # Async tool(s)
└── run_worker.py is project/run_worker.py
```

## Running

```bash
agentex agents run --manifest manifest.yaml
```

Open the Temporal UI at http://localhost:8080 to watch the workflow and the
`agent` activity execute. Use `dev.ipynb` to create a task and send messages.

## Adding tools

Define an **async** `@tool` in `project/tools.py` and add it to `TOOLS`. The
model is bound with `TOOLS` and the tool node runs them by name.

For a fuller version with human-in-the-loop approval and graph-introspection
queries, scaffold the `temporal-langgraph` template via `agentex init`.

## Tests

- `tests/test_graph_temporal.py` — hermetic ReAct-loop test with a stub model,
  plus a live end-to-end run through the real Temporal plugin (skipped unless
  `LITELLM_API_KEY` is set).
- `tests/test_agent.py` — live integration against a running agent.
