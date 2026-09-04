# Claude Agents SDK Integration with AgentEx

Integration of Claude Agents SDK with AgentEx's Temporal-based orchestration platform. Claude agents run in durable workflows with real-time streaming to the AgentEx UI.

> ⚠️ **Note**: This integration is designed for local agent development and single-worker deployments. For distributed multi-worker Kubernetes deployments, additional infrastructure is required (see [Deployment Considerations](#deployment-considerations) below).

## Features

- **Durable Execution** - Workflows survive restarts via Temporal's event sourcing (single-worker)
- **Session Resume** - Conversation context maintained across turns via `session_id`
- **Workspace Isolation** - Each task gets dedicated directory for file operations
- **Real-time Streaming** - Text and tool calls stream to UI via Redis
- **Tool Execution** - Read, Write, Edit, Bash, Grep, Glob with visibility in UI
- **Subagents** - Specialized agents (code-reviewer, file-organizer) with nested tracing
- **Cost Tracking** - Token usage and API costs logged per turn
- **Automatic Retries** - Temporal policies handle transient failures

## How It Works

### Architecture

```
┌─────────────────────────────────┐
│  Temporal Workflow              │
│  - Stores session_id in state   │
│  - Tracks turn number           │
│  - Sets _task_id, _trace_id     │
└────────────┬────────────────────┘
             │ execute_activity
             ↓
┌─────────────────────────────────┐
│  run_claude_agent_activity      │
│  - Reads context from ContextVar│
│  - Configures Claude SDK        │
│  - Processes messages via hooks │
│  - Returns session_id           │
└────────────┬────────────────────┘
             │ ClaudeSDKClient
             ↓
┌─────────────────────────────────┐
│  Claude SDK                     │
│  - Maintains session            │
│  - Calls Anthropic API          │
│  - Executes tools in workspace  │
│  - Triggers hooks               │
└─────────────────────────────────┘
```

### Context Threading

The integration reuses AgentEx's `ContextInterceptor` pattern (originally built for OpenAI):

1. **Workflow** stores `_task_id`, `_trace_id`, `_parent_span_id` as instance variables
2. **ContextInterceptor (outbound)** reads these from workflow instance, injects into activity headers
3. **ContextInterceptor (inbound)** extracts from headers, sets `ContextVar` values
4. **Activity** reads `ContextVar` to get task_id for streaming

This enables real-time streaming without breaking Temporal's determinism requirements.

### Session Management

Claude SDK sessions are preserved across turns:

1. **First turn**: Claude SDK creates session, returns `session_id` in `SystemMessage`
2. **Message handler** extracts `session_id` from messages
3. **Activity** returns `session_id` to workflow
4. **Workflow** stores in `StateModel.claude_session_id` (Temporal checkpoints this)
5. **Next turn**: Pass `resume=session_id` to `ClaudeAgentOptions`
6. **Claude SDK** resumes session with full conversation history

### Tool Streaming via Hooks

Tool lifecycle events are handled by Claude SDK hooks:

**PreToolUse Hook**:
- Called before tool execution
- Streams `ToolRequestContent` to UI → shows "Using tool: Write"
- Creates nested span for Task tool (subagents)

**PostToolUse Hook**:
- Called after tool execution
- Streams `ToolResponseContent` to UI → shows "Used tool: Write"
- Closes subagent spans with results

### Subagent Execution

Subagents are defined as `AgentDefinition` objects passed to Claude SDK:

```python
agents={
    'code-reviewer': AgentDefinition(
        description='Expert code review specialist...',
        prompt='You are a code reviewer...',
        tools=['Read', 'Grep', 'Glob'],  # Read-only
        model='sonnet',
    )
}
```

When Claude uses the Task tool, the SDK routes to the appropriate subagent based on description matching. Subagent execution is tracked via nested tracing spans.

## Code Structure

```
claude_agents/
├── __init__.py                 # Public exports
├── activities.py               # Temporal activities
│   ├── create_workspace_directory
│   └── run_claude_agent_activity
├── message_handler.py          # Message processing
│   └── ClaudeMessageHandler
│       ├── Streams text blocks
│       ├── Extracts session_id
│       └── Extracts usage/cost
└── hooks/
    └── hooks.py                # Claude SDK hooks
        └── TemporalStreamingHooks
            ├── pre_tool_use
            └── post_tool_use
```

## Deployment Considerations

This integration works well for local development and single-worker deployments. For distributed multi-worker production deployments, consider the following:

### ⚠️ Session Persistence (Multi-Worker)

**Current behavior**: Claude SDK sessions are tied to the worker process.

- **Local dev**: ✅ Works - session persists within single worker
- **K8s multi-pod**: ⚠️ Session ID stored in Temporal state, but session itself lives in Claude CLI process
- **Impact**: If task moves to different pod, session becomes invalid
- **Infrastructure needed**: Session persistence layer or sticky routing to same pod

### ⚠️ Workspace Storage (Multi-Worker)

**Current behavior**: Workspaces are local directories (`./workspace/{task_id}`).

- **Local dev**: ✅ Works - single worker accesses all files
- **K8s multi-pod**: ⚠️ Each pod has isolated filesystem
- **Impact**: Files created by one pod are invisible to other pods
- **Infrastructure needed**: Shared storage (NFS, EFS, GCS Fuse) via `CLAUDE_WORKSPACE_ROOT` env var

**Solution for production**:
```bash
# Mount shared filesystem (NFS, EFS, etc.) to all pods
export CLAUDE_WORKSPACE_ROOT=/mnt/shared/workspaces

# All workers will now share workspace access
```

### ℹ️ Filesystem-Based Configuration

**Current approach**: Agents and configuration are defined programmatically in code.

- **Not used**: `.claude/agents/`, `.claude/skills/`, `CLAUDE.md` files
- **Why**: Aligns with AgentEx's code-as-configuration philosophy
- **Trade-off**: More explicit and version-controlled, but can't leverage existing Claude configs
- **To enable**: Would need to add `setting_sources=["project"]` to `ClaudeAgentOptions`

**Current approach** (programmatic config in workflow.py):
```python
subagents = {
    'code-reviewer': AgentDefinition(
        description='...',
        prompt='...',
        tools=['Read', 'Grep', 'Glob'],
        model='sonnet',
    ),
}
```

---

**Summary**: The integration is production-ready for **single-worker deployments**. Multi-worker deployments require additional infrastructure for session persistence and workspace sharing.

## Quick Start

### Prerequisites

- Temporal server (localhost:7233)
- Redis (localhost:6379)
- Anthropic API key

### Run

```bash
# Install
rye sync --all-features

# Configure
export ANTHROPIC_API_KEY="your-key"
export REDIS_URL="redis://localhost:6379"
export TEMPORAL_ADDRESS="localhost:7233"

# Run from repository root
uv run agentex agents run --manifest examples/tutorials/10_async/10_temporal/090_claude_agents_sdk_mvp/manifest.yaml
```

## Example Interactions

### Context Preservation

```
User: "Your name is Jose"
Claude: "Nice to meet you! I'm Jose..."

User: "What name did I assign to you?"
Claude: "You asked me to go by Jose!"  ← Remembers context
```

### Tool Usage

```
User: "Create a hello.c file with Hello World"
Claude: *streams response*
[Tool card appears: "Using tool: Write"]
[Tool card updates: "Used tool: Write"]
"Done! I've created hello.c..."
```

### Subagents

```
User: "Review the code quality in hello.c"
Claude: *delegates to code-reviewer*
[Tool card: "Using tool: Task" with subagent_type: "code-reviewer"]
[Traces view shows: "Subagent: code-reviewer" nested under turn]
```

## Behind the Scenes

### Message Flow

When a user sends a message:

1. **Signal received** (`on_task_event_send`) - Workflow increments turn, echoes message
2. **Span created** - Tracing span wraps turn, stores `parent_span_id` for interceptor
3. **Activity called** - Workflow passes prompt, workspace, session_id, subagent defs
4. **Context threaded** - Interceptor injects task_id/trace_id into activity headers
5. **Activity starts** - Reads context from ContextVar, creates hooks
6. **Claude executes** - SDK uses hooks to stream tools, message_handler streams text
7. **Results returned** - Activity returns session_id, usage, cost
8. **State updated** - Workflow stores session_id for next turn

### Streaming Pipeline

**Text streaming**:
```
Claude SDK → TextBlock → ClaudeMessageHandler._handle_text_block()
→ TextDelta → adk.streaming.stream_update()
→ Redis XADD → AgentEx UI
```

**Tool streaming**:
```
Claude SDK → PreToolUse hook → ToolRequestContent
→ adk.streaming (via hook) → Redis → UI ("Using tool...")

Tool executes...

Claude SDK → PostToolUse hook → ToolResponseContent
→ adk.streaming (via hook) → Redis → UI ("Used tool...")
```

### Subagent Tracing

When Task tool is detected in PreToolUse hook:

```python
# Create nested span
span_ctx = adk.tracing.span(
    trace_id=trace_id,
    parent_id=parent_span_id,
    name=f"Subagent: {subagent_type}",
    input=tool_input,
)
span = await span_ctx.__aenter__()

# Store for PostToolUse to close
self.subagent_spans[tool_use_id] = (span_ctx, span)
```

In PostToolUse hook, the span is closed with results, creating a complete nested trace.

## Key Implementation Details

### Temporal Determinism

- **File I/O in activities**: `create_workspace_directory` is an activity (not workflow code)
- **Message iteration completes**: Use `receive_response()` (not `receive_messages()`)
- **State is serializable**: `StateModel` uses Pydantic BaseModel

### AgentDefinition Serialization

Temporal serializes activity arguments to JSON. AgentDefinition dataclasses become dicts, so the activity reconstructs them:

```python
agent_defs = {
    name: AgentDefinition(**agent_data)
    for name, agent_data in agents.items()
}
```

### Hook Callback Signatures

Claude SDK expects specific signatures:

```python
async def pre_tool_use(
    input_data: dict[str, Any],  # Contains tool_name, tool_input
    tool_use_id: str | None,     # Unique ID for this call
    context: Any,                # HookContext (currently unused)
) -> dict[str, Any]:             # Return {} to allow, or modify behavior
```

## Comparison with OpenAI Integration

| Aspect | OpenAI | Claude |
|--------|--------|--------|
| **Plugin** | `OpenAIAgentsPlugin` (official) | Manual activity wrapper |
| **Streaming** | Token-level deltas | Message block-level |
| **Tool Results** | `ToolResultBlock` | `UserMessage` (with acceptEdits) |
| **Hooks** | `RunHooks` class | `HookMatcher` with callbacks |
| **Context Threading** | ContextInterceptor | ContextInterceptor (reused!) |
| **Subagents** | Agent handoffs | AgentDefinition config |

## Notes

**Message Block Streaming**: Claude SDK returns complete text blocks, not individual tokens. Text appears instantly rather than animating character-by-character. This is inherent to Claude SDK's API design.

**In-Process Subagents**: Subagents run within Claude SDK via config-based routing, not as separate Temporal workflows. This is by design - subagents are specializations, not independent agents.

**Manual Activity Calls**: Unlike OpenAI which has an official Temporal plugin, Claude integration requires explicit `workflow.execute_activity()` calls. A future enhancement could create an automatic plugin.

## License

Apache 2.0 (same as AgentEx SDK)
