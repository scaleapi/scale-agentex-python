# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Package Management in the top level repo
- Use `rye` for dependency management (preferred)
- Run `./scripts/bootstrap` to set up the environment
- Or use `rye sync --all-features` directly

Special note: the individual tutorials maintain their own tutorial specific virtualenv using `uv`. So when testing/running tutorials, you `uv run` instead of `rye run`.  Everything else is similar.

#### Testing
- Run tests: `rye run pytest` or `./scripts/test`
- Run specific test: `rye run pytest path/to/test_file.py::TestClass::test_method -v`
- Mock server is automatically started for tests, runs on port 4010

#### Linting and Formatting
- Format code: `rye run format` or `./scripts/format`
  * The repository is still in flux, so running format might accidentally change files that aren't part of your scope of changes. So always run `run rye format` with additional arguments to constrain the formatting to the files that you are modifying.
- Lint code: `rye run lint` or `./scripts/lint`
- Type check: `rye run typecheck` (runs both pyright and mypy)

### Building and Running
- Build package: `rye build`



### CLI Commands
The package provides the `agentex` CLI with these main commands:
- `agentex agents` - Get, list, run, build, and deploy agents
- `agentex tasks` - Get, list, and delete tasks  
- `agentex secrets` - Sync, get, list, and delete secrets
- `agentex uv` - UV wrapper with AgentEx-specific enhancements
- `agentex init` - Initialize new agent projects

### Agent Development
- Run agents: `agentex agents run --manifest manifest.yaml`
- Debug agents: `agentex agents run --manifest manifest.yaml --debug-worker`
- Debug with custom port: `agentex agents run --manifest manifest.yaml --debug-worker --debug-port 5679`

### Custom OpenAI Client for Agents SDK

Configure custom OpenAI clients **specifically for the OpenAI Agents SDK** integration (Agent and Runner classes).

⚠️ **Scope**: This configuration ONLY affects OpenAI Agents SDK operations. It does NOT affect:
- LiteLLM integration (configure LiteLLM separately via environment variables or LiteLLM config)
- SGP integration
- Direct OpenAI API calls

#### Requirements
- Must use **async** client: `AsyncOpenAI` or `AsyncAzureOpenAI`
- Sync clients (`OpenAI`) are not supported by the Agents SDK

#### Basic Usage (Custom Endpoint)

Use this for custom OpenAI-compatible endpoints such as LiteLLM proxy for cost tracking:

```python
from openai import AsyncOpenAI
from agentex.lib.adk.providers._modules.openai_agents_config import (
    initialize_openai_agents_client
)

# Configure custom endpoint
client = AsyncOpenAI(
    base_url="https://your-proxy.com/v1",
    api_key=os.getenv("CUSTOM_API_KEY")
)
initialize_openai_agents_client(client)
```

#### Azure OpenAI

```python
from openai import AsyncAzureOpenAI
from agentex.lib.adk.providers._modules.openai_agents_config import (
    initialize_openai_agents_client
)

client = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-02-01"
)
initialize_openai_agents_client(client)
```

#### Temporal Workers

Call `initialize_openai_agents_client()` in your worker startup script **BEFORE** starting the worker:

```python
# run_worker.py
import os
from openai import AsyncOpenAI
from agentex.lib.adk.providers._modules.openai_agents_config import (
    initialize_openai_agents_client
)

# Step 1: Configure client before starting worker
if os.getenv("CUSTOM_OPENAI_BASE_URL"):
    client = AsyncOpenAI(
        base_url=os.getenv("CUSTOM_OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY")
    )
    initialize_openai_agents_client(client)

# Step 2: Start worker (all agent operations will use configured client)
# ... worker startup code ...
```

#### Backward Compatibility

If `initialize_openai_agents_client()` is not called, the OpenAI Agents SDK uses default OpenAI configuration via the `OPENAI_API_KEY` environment variable. All existing code continues to work without changes.

## Architecture Overview

### Code Structure
- `/src/agentex/` - Core SDK and generated API client code
- `/src/agentex/lib/` - Custom library code (not modified by code generator)
  - `/cli/` - Command-line interface implementation
  - `/core/` - Core services, adapters, and temporal workflows
  - `/sdk/` - SDK utilities and FastACP implementation
  - `/types/` - Custom type definitions
  - `/utils/` - Utility functions
- `/examples/` - Example implementations and tutorials
- `/tests/` - Test suites

### Key Components

**SDK Architecture:**
- **Client Layer**: HTTP client for AgentEx API (`_client.py`, `resources/`)
- **CLI Layer**: Typer-based command interface (`lib/cli/`)
- **Core Services**: Temporal workflows, adapters, and services (`lib/core/`)
- **FastACP**: Fast Agent Communication Protocol implementation (`lib/sdk/fastacp/`)
- **State Machine**: Workflow state management (`lib/sdk/state_machine/`)

**Temporal Integration:**
- Workflow definitions in `lib/core/temporal/`
- Activity definitions for different providers
- Worker implementations for running temporal workflows

**Agent Framework:**
- Manifest-driven agent configuration
- Support for multiple agent types (sync, temporal-based)
- Debugging support with VS Code integration

### Code Generation
Most SDK code is auto-generated. Manual changes are preserved in:
- `src/agentex/lib/` directory
- `examples/` directory
- Merge conflicts may occur between manual patches and generator changes

### Key Dependencies
- `temporalio` - Temporal workflow engine
- `typer` - CLI framework  
- `pydantic` - Data validation
- `httpx` - HTTP client
- `fastapi` - Web framework
- `ruff` - Linting and formatting
- `pytest` - Testing framework

### Environment Requirements
- Python 3.12+ required
- Uses Rye for dependency management
- Supports both sync and async client patterns