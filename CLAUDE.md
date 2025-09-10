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