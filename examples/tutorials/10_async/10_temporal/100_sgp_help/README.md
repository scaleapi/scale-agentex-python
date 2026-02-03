# SGP Help Agent

An AI agent that answers questions about the Scale Generative Platform (SGP) codebase by searching multiple GitHub repositories and providing answers with citations.

## Overview

The SGP Help Agent clones and searches three SGP repositories:
- **scaleapi** - Scale API repository (focus: `packages/egp-api-backend/`, `packages/egp-annotation/`)
- **sgp** - SGP core platform
- **sgp-solutions** - Example implementations and solutions

The agent operates in read-only mode, using tools like Read, Grep, Glob, and Bash (git commands) to explore the codebase and answer questions with GitHub URL citations.

## Features

- **Multi-repo workspace**: Clones 3 SGP repos on task initialization with smart caching
- **Read-only operation**: No code editing, focused on answering questions
- **Citation-focused**: Provides GitHub URLs for all code references
- **MCP integration**: Uses SGP docs MCP server for documentation queries
- **Session continuity**: Maintains conversation context across multiple turns
- **Smart caching**: Uses shared cache to minimize network traffic

## Architecture

Built on:
- **Claude Agents SDK**: Powers the AI agent with tool use
- **Temporal workflows**: Provides durable execution and retry logic
- **AgentEx SDK**: Provides ACP integration and streaming

Key components:
- `workflow.py` - SGPHelpWorkflow for orchestration
- `activities.py` - Git operations (setup_sgp_repos activity)
- `run_worker.py` - Temporal worker registration
- `acp.py` - ACP server setup

## Example Questions

Try asking:
- "Where is the SGP API client implemented?"
- "Show me examples from sgp-solutions"
- "How does authentication work in the backend?"
- "What annotation features are available?"
- "Where is the error handling in the API backend?"

## Local Development

### Prerequisites

- Python 3.12+
- Rye or UV for dependency management
- Temporal server running (via docker compose)
- Redis running
- Anthropic API key

### Setup

1. Set environment variables:
```bash
export ANTHROPIC_API_KEY=your-key-here
export REDIS_URL=redis://localhost:6379
```

2. Run the agent:
```bash
agentex agents run --manifest manifest.yaml --debug-worker
```

3. Create a task via API and send questions

### Debug Mode

To debug the worker:
```bash
agentex agents run --manifest manifest.yaml --debug-worker --debug-port 5679
```

Then attach VS Code debugger to port 5679.

## Directory Structure

```
100_sgp_help/
├── manifest.yaml          # Agent configuration
├── pyproject.toml         # Dependencies
├── Dockerfile             # Container image
├── .dockerignore          # Docker ignore rules
├── project/
│   ├── acp.py            # ACP server
│   ├── workflow.py       # SGPHelpWorkflow
│   ├── activities.py     # Git operations activity
│   └── run_worker.py     # Worker registration
├── tests/
│   └── test_sgp_agent.py # Test suite
└── README.md             # This file
```

## Workspace Structure

When a task is created, the agent sets up:

```
.claude-workspace/
├── .repos-cache/          # Shared cache (reused across tasks)
│   ├── scaleapi/
│   ├── sgp/
│   └── sgp-solutions/
└── {task-id}/
    └── repos/             # Task-specific clones (working directory)
        ├── scaleapi/
        ├── sgp/
        └── sgp-solutions/
```

The agent's `cwd` is set to `repos/` so it can access all three repositories.

## System Prompt

The agent uses a specialized system prompt that:
- Identifies itself as an SGP expert
- Explains the workspace structure and repo focus areas
- Requires GitHub URL citations for all code references
- Enforces read-only mode
- Guides multi-repo search strategy

## Caching Strategy

To minimize network traffic and improve performance:
1. **Cache directory**: Shared across all tasks at `.repos-cache/`
2. **Initial clone**: `git clone --depth=1` to cache (only latest commit)
3. **Cache update**: `git fetch origin` + `git reset --hard origin/HEAD`
4. **Task clone**: `git clone --depth=1 file://{cache_path}` (local, fast)

## MCP Integration

The agent is configured to use the SGP docs MCP server:
- URL: https://docs.gp.scale.com/mcp
- Transport: SSE (Server-Sent Events)

Note: MCP integration depends on Claude Agent SDK support for HTTP/SSE transports.

## Testing

Run the test suite:
```bash
cd examples/tutorials/10_async/10_temporal/100_sgp_help
uv run pytest tests/test_sgp_agent.py -v
```

## Performance

Typical timings:
- Repo setup (first time): 2-3 minutes
- Repo setup (cached): 30-60 seconds
- First response: 20-30 seconds
- Follow-up responses: 5-10 seconds

## Limitations

1. **MCP Transport**: HTTP/SSE MCP configuration format requires Claude Agent SDK support
2. **Cache freshness**: Repos cached indefinitely (no automatic updates)
3. **Shallow clones**: Only latest commit available (no full git history)
4. **Citation accuracy**: Relies on system prompt compliance

## Future Enhancements

- Subagents for specialized tasks (code-expert, docs-expert, solutions-expert)
- Auto-citation post-processing hooks
- Smart cache with TTL and auto-refresh
- Multi-branch/tag support
- Git blame integration for authorship tracking
- Cache locking for concurrent worker safety

## Deployment

Build and push the Docker image:
```bash
agentex agents build --manifest manifest.yaml
agentex agents deploy --manifest manifest.yaml
```

Ensure secrets are configured:
- `anthropic-api-key` (key: `api-key`)
- `redis-url-secret` (key: `url`)

## License

Same as parent project (agentex-sdk).
