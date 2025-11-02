# Temporal Tutorials

Build durable, production-ready agents with Temporal workflows. These tutorials show you how to combine Temporal's durability guarantees with modern agent frameworks.

## Tutorial Structure

### Core Temporal Patterns (No Agent Framework)
- **[000_hello_acp](./000_hello_acp/)** - Your first Temporal workflow agent. Learn the basics of workflows, signals, and durability.

### OpenAI Agents SDK + Temporal Integration
Tutorials showing how to integrate the OpenAI Agents SDK with Temporal workflows:

- **[010_open_ai_agents_sdk_hello_world](./010_open_ai_agents_sdk_hello_world/)** - Hello world with OpenAI Agents SDK and Temporal streaming
- **[020_open_ai_agents_sdk_tools](./020_open_ai_agents_sdk_tools/)** - Adding tools to your agent (calculator, file operations)
- **[030_open_ai_agents_sdk_human_in_the_loop](./030_open_ai_agents_sdk_human_in_the_loop/)** - Human approval patterns for sensitive operations
- **[040_workflow_activities](./040_workflow_activities/)** - Using Temporal activities for workflow orchestration (database, notifications, reports)
- **[050_state_machines](./050_state_machines/)** - Complex multi-phase workflows with state machines and MCP servers

## Prerequisites

1. **Development Environment**
   - Python 3.12+
   - Backend services running: `make dev` from repository root
   - Temporal UI available at http://localhost:8233

2. **API Keys** (for OpenAI SDK tutorials 010-050)
   - OpenAI API key: Set `OPENAI_API_KEY` environment variable

## Quick Start

Each tutorial is self-contained. To run any tutorial:

```bash
cd examples/tutorials/10_agentic/10_temporal/<tutorial-name>
export OPENAI_API_KEY="your-key-here"  # Only needed for 010-050
uv run agentex agents run --manifest manifest.yaml
```

## Learning Path

**New to Temporal?** Start here:
1. [000_hello_acp](./000_hello_acp/) - Learn Temporal basics
2. [010_open_ai_agents_sdk_hello_world](./010_open_ai_agents_sdk_hello_world/) - Add OpenAI Agents SDK

**Want to build production agents?** Follow this path:
1. [010_open_ai_agents_sdk_hello_world](./010_open_ai_agents_sdk_hello_world/) - Basic agent
2. [020_open_ai_agents_sdk_tools](./020_open_ai_agents_sdk_tools/) - Add tools
3. [030_open_ai_agents_sdk_human_in_the_loop](./030_open_ai_agents_sdk_human_in_the_loop/) - Add safety
4. [040_workflow_activities](./040_workflow_activities/) - Add orchestration
5. [050_state_machines](./050_state_machines/) - Add complex workflows

## Key Concepts

### Temporal Workflows
Workflows are durable, resumable functions that survive crashes and can run for days/months/years without consuming resources while idle.

### OpenAI Agents SDK
The OpenAI Agents SDK provides a framework for building agentic applications with streaming, tool calling, and handoffs. When combined with Temporal, you get both powerful agent capabilities and enterprise durability.

### Activities
Activities are functions that interact with external systems (databases, APIs, file systems). They can be retried independently of the workflow.

### MCP Servers
Model Context Protocol (MCP) servers provide tools and context to agents. Tutorial 050 shows how to integrate MCP servers (time, web search, fetch) with Temporal workflows.

## Monitoring

All tutorials include Temporal UI integration. While your agent is running, visit:
- **Temporal UI**: http://localhost:8233
- See workflows, activities, and state transitions in real-time

## Common Patterns

### Streaming Responses
Tutorials 010-050 show real-time streaming of agent responses using `TemporalStreamingModelProvider`.

### State Management
Tutorial 050 demonstrates complex state machines with multiple phases and sub-workflows.

### Tool Integration
- Tutorial 020: Activities AS agent tools
- Tutorial 040: Activities FOR workflow orchestration

## Need Help?

- Check individual tutorial READMEs for detailed explanations
- Visit the [main repo documentation](https://github.com/scaleapi/scale-agentex)
- Open an issue if you find bugs or have questions
