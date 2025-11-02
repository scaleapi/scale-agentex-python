# [Temporal] State Machines

**Part of the [OpenAI SDK + Temporal integration series](../README.md)** → Previous: [040 Workflow Activities](../040_workflow_activities/)

Build complex multi-state workflows using state machines with Temporal. This tutorial shows a "deep research" agent that transitions through states: clarify query → wait for input → perform research → complete.

## What You'll Learn
- Building state machines with Temporal sub-workflows
- Integrating MCP servers (time, web search, fetch) with OpenAI Agents SDK
- Explicit state transitions and phase management
- When to use state machines vs simple workflows
- Handling complex multi-phase agent behaviors with streaming

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Temporal UI available at http://localhost:8233
- OpenAI API key configured
- Understanding of OpenAI Agents SDK (see [010](../010_open_ai_agents_sdk_hello_world/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/050_state_machines
export OPENAI_API_KEY="your-key-here"
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8233 to see state transitions and sub-workflows.

## Architecture

The workflow uses three sub-workflows, each handling a specific state:
- `ClarifyUserQueryWorkflow` - Asks follow-up questions to understand user intent
- `WaitingForUserInputWorkflow` - Waits for user responses
- `PerformingDeepResearchWorkflow` - Executes the research using OpenAI Agents SDK with MCP servers

State transitions are explicit and tracked, with each sub-workflow handling its own logic.

### MCP Server Integration

This tutorial demonstrates integrating MCP (Model Context Protocol) servers with Temporal workflows:
- **mcp-server-time**: Provides current time in different timezones
- **openai-websearch-mcp**: Enables web search capabilities
- **mcp-server-fetch**: Fetches content from URLs

MCP servers are registered with the worker and made available to agents via `openai_agents_workflow.stateless_mcp_server()`.

## Why State Machines Matter

Complex agents often need to:
- Wait for user input at specific points
- Branch behavior based on conditions
- Orchestrate multiple steps with clear transitions
- Resume at the exact state after failures

State machines provide this structure. Each state is a sub-workflow, and Temporal ensures transitions are durable and resumable.

## Key Patterns

### State Machine Pattern
```python
self.state_machine = DeepResearchStateMachine(
    initial_state=DeepResearchState.WAITING_FOR_USER_INPUT,
    states=[
        State(name=DeepResearchState.CLARIFYING, workflow=ClarifyWorkflow()),
        State(name=DeepResearchState.RESEARCHING, workflow=ResearchWorkflow()),
    ]
)

await self.state_machine.transition(DeepResearchState.RESEARCHING)
```

### MCP Server Pattern
```python
# In run_worker.py - register MCP servers
MCP_SERVERS = [
    StatelessMCPServerProvider(
        lambda: MCPServerStdio(
            name="openai-websearch-mcp",
            params={...},
            client_session_timeout_seconds=120,
        )
    ),
]

worker = AgentexWorker(
    task_queue=task_queue_name,
    mcp_server_providers=MCP_SERVERS,
    ...
)

# In workflow - use MCP servers
websearch = openai_agents_workflow.stateless_mcp_server("openai-websearch-mcp")
agent = Agent(
    name="Research Agent",
    mcp_servers=[websearch],
)
```

This is an advanced pattern - only needed when your agent has complex, multi-phase behavior.

## When to Use
- Multi-step processes with clear phases (research, analysis, reporting)
- Workflows that wait for user input at specific points
- Operations with branching logic based on state
- Complex coordination patterns requiring explicit transitions
- Agents that need external tools/data sources (via MCP)

## Why This Matters
State machines provide structure for complex agent behaviors. While simple agents can use basic workflows, complex agents benefit from explicit state management. Temporal ensures state transitions are durable and resumable, even after failures. MCP integration adds powerful tool capabilities without vendor lock-in.

## Key Files
- `project/workflow.py` - Main workflow with state machine orchestration
- `project/run_worker.py` - Worker setup with MCP server registration
- `project/state_machines/deep_research.py` - State machine definition
- `project/workflows/deep_research/` - Sub-workflow implementations

**Back to:** [Tutorial Index](../README.md)
