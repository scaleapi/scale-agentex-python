# [Temporal] State Machine

Build complex multi-state workflows using state machines with Temporal. This tutorial shows a "deep research" agent that transitions through states: clarify query → wait for input → perform research → wait for follow-ups.

## What You'll Learn
- Building state machines with Temporal sub-workflows
- Explicit state transitions and phase management
- When to use state machines vs simple workflows
- Handling complex multi-phase agent behaviors

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Temporal UI available at http://localhost:8233
- Understanding of Temporal workflows (see [010_agent_chat](../010_agent_chat/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/020_state_machine
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8233 to see state transitions and sub-workflows.

## Architecture

The workflow uses three sub-workflows, each handling a specific state:
- `ClarifyUserQueryWorkflow` - Asks follow-up questions to understand user intent
- `WaitingForUserInputWorkflow` - Waits for user responses
- `PerformingDeepResearchWorkflow` - Executes the research with full context

State transitions are explicit and tracked, with each sub-workflow handling its own logic.

## Why State Machines Matter

Complex agents often need to:
- Wait for user input at specific points
- Branch behavior based on conditions
- Orchestrate multiple steps with clear transitions
- Resume at the exact state after failures

State machines provide this structure. Each state is a sub-workflow, and Temporal ensures transitions are durable and resumable.

## Key Pattern

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

This is an advanced pattern - only needed when your agent has complex, multi-phase behavior.

## When to Use
- Multi-step processes with clear phases
- Workflows that wait for user input at specific points
- Operations with branching logic based on state
- Complex coordination patterns requiring explicit transitions

## Why This Matters
State machines provide structure for complex agent behaviors. While simple agents can use basic workflows, complex agents benefit from explicit state management. Temporal ensures state transitions are durable and resumable, even after failures.

**Next:** [030_custom_activities](../030_custom_activities/) - Extend workflows with custom activities
