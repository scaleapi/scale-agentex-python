# Claude Agents SDK Integration with AgentEx

## Overview

Complete working integration of Claude Agents SDK with AgentEx's Temporal-based orchestration platform. This tutorial demonstrates how to run Claude-powered agents in durable, observable Temporal workflows with real-time streaming to the AgentEx UI.

## Features ✅

### Core Functionality
- ✅ **Temporal Workflow Integration** - Claude agents run in durable workflows (survive restarts, full replay)
- ✅ **Workspace Isolation** - Each task gets isolated directory for file operations
- ✅ **Session Management** - Conversation context maintained across turns via session resume
- ✅ **Real-time Streaming** - Messages and tool calls stream to UI via Redis

### Tool Support
- ✅ **File Operations** - Read, Write, Edit files with workspace isolation
- ✅ **Command Execution** - Bash commands execute within workspace
- ✅ **File Search** - Grep and Glob for finding files and patterns
- ✅ **Tool Visibility** - Tool cards show in UI with parameters and results

### Advanced Features
- ✅ **Subagent Support** - Specialized agents via Task tool (code-reviewer, file-organizer)
- ✅ **Nested Tracing** - Subagent execution tracked as child spans in traces view
- ✅ **Cost Tracking** - Token usage and API costs logged per turn
- ✅ **Automatic Retries** - Temporal retry policies for transient failures

## Known Limitations

### Streaming Behavior
- **Message blocks vs token streaming**: Claude SDK returns complete text blocks rather than individual tokens. Text appears instantly instead of animating character-by-character. This is a Claude SDK API limitation, not an integration issue.
- **UI message ordering**: Frontend may reorder text and tool cards (cosmetic issue in AgentEx UI)

### Architecture Choices
- **Manual activity wrapping**: Activities are explicitly called (no automatic plugin yet)
- **In-process subagents**: Subagents run within Claude SDK (not as separate Temporal workflows)
- **Basic error handling**: All errors use Temporal's retry policy (no error categorization)

## Quick Start

### Prerequisites

1. **Temporal server** running (localhost:7233)
2. **Redis** running (localhost:6379)
3. **Anthropic API key**

### Setup

1. **Install dependencies:**
   ```bash
   cd /Users/prassanna.ravishankar/git/agentex-python-claude-agents-sdk
   rye sync --all-features
   ```

2. **Set environment variables:**
   ```bash
   export ANTHROPIC_API_KEY="your-anthropic-api-key"
   export REDIS_URL="redis://localhost:6379"
   export TEMPORAL_ADDRESS="localhost:7233"
   ```

3. **Run the worker:**
   ```bash
   cd examples/tutorials/10_async/10_temporal/090_claude_agents_sdk_mvp/project
   rye run python run_worker.py
   ```

4. **In another terminal, run the ACP server:**
   ```bash
   cd examples/tutorials/10_async/10_temporal/090_claude_agents_sdk_mvp/project
   rye run python acp.py
   ```

5. **Create a task via AgentEx API** (or use the AgentEx dashboard)

## Architecture

```
User Message
    ↓
Workflow (ClaudeMvpWorkflow)
    ├─ Creates workspace: /workspaces/{task_id}
    ├─ Stores task_id in instance var
    └─ Calls activity ↓

Activity (run_claude_agent_activity)
    ├─ Reads task_id from ContextVar (set by ContextInterceptor)
    ├─ Configures Claude SDK with workspace
    ├─ Runs Claude SDK
    ├─ Streams text to Redis (via adk.streaming)
    └─ Returns complete messages for Temporal

Claude SDK (ClaudeSDKClient)
    ├─ Executes with cwd=/workspaces/{task_id}
    ├─ Tools operate on workspace filesystem
    └─ Calls Anthropic API

Anthropic API
    ↓
Streaming Response
    ├─ Tokens stream to Redis → UI (real-time)
    └─ Complete response to Temporal (determinism)
```

### Key Innovation: Context Threading

The magic is **ContextInterceptor** (reused from OpenAI plugin):

1. **Workflow** stores `task_id` in instance variable
2. **ContextInterceptor** (outbound) reads `task_id` from workflow instance, injects into activity headers
3. **ContextInterceptor** (inbound) extracts `task_id` from headers, sets ContextVar
4. **Activity** reads `task_id` from ContextVar, uses for streaming

This allows streaming WITHOUT breaking Temporal's determinism!

## Example Usage

### Basic Chat

```
User: "Hello! Can you create a hello.py file?"

Claude: *streams response in real-time*
"I'll create a hello.py file for you.

[Uses Write tool to create file]

I've created hello.py with a simple hello world program."
```

### File Operations

```
User: "List all files in the workspace"

Claude: *uses Bash tool*
"Here are the files:
- hello.py
- README.md"
```

### Code Modification

```
User: "Add a main function to hello.py"

Claude: *uses Edit tool*
"I've added a main function to hello.py..."
```

### Subagents (Task Tool)

The workflow includes two specialized subagents:

**1. code-reviewer** - Read-only code analysis
```
User: "Review the code quality in hello.py"

Claude: *delegates to code-reviewer subagent*
[Uses Task tool → code-reviewer]
- Specialized prompt for code review
- Limited to Read, Grep, Glob tools
- Returns thorough analysis
```

**2. file-organizer** - Project structuring
```
User: "Create a well-organized Python project structure"

Claude: *delegates to file-organizer subagent*
[Uses Task tool → file-organizer]
- Specialized prompt for file organization
- Can use Write, Bash tools
- Uses faster Haiku model
```

**Subagent visibility**:
- Tool cards show "Using tool: Task" with subagent parameters
- Traces view shows nested spans: `Subagent: code-reviewer`
- Timing and cost tracked separately per subagent

## Architecture Details

### Workspace Isolation

Each task gets an isolated workspace:
- Location: `/workspaces/{task_id}/`
- Created on workflow start
- Claude's `cwd` points to this directory
- All file operations happen within workspace

### Streaming Flow

1. Activity creates `streaming_task_message_context`
2. Loops through Claude SDK messages
3. Extracts text from `TextBlock` content
4. Creates `TextDelta` and streams via `stream_update`
5. Redis carries stream to UI subscribers
6. Activity returns complete messages to Temporal

### Error Handling

Currently minimal:
- All errors bubble up to Temporal
- Temporal retry policy: 3 attempts, exponential backoff
- No distinction between retriable/non-retriable errors

## Limitations & Tradeoffs

### Manual Activity Wrapping

**Current**: Workflow explicitly calls `workflow.execute_activity(run_claude_agent_activity, ...)`
**Future**: Automatic plugin wraps `ClaudeSDKClient.query()` calls

This works for MVP but is less elegant than OpenAI integration.

### No Tool Call Streaming

**Current**: Tool calls (Read, Write, Bash) execute but aren't streamed to UI
**Future**: Hook into tool lifecycle and stream `ToolRequestContent`/`ToolResponseContent`

Users see final result but not intermediate tool usage.

### Text-Only Streaming

**Current**: Only text content streams
**Future**: Stream reasoning, tool calls, errors

Sufficient for MVP, richer content later.

### No Subagents

**Current**: Claude's Task tool is disabled
**Future**: Intercept Task tool and spawn child Temporal workflows

Can't do recursive agents yet.

## Debugging

### Check Worker Logs

```bash
# Worker logs show:
# - Activity starts/completions
# - Claude SDK calls
# - Streaming context creation
# - Errors
```

### Check Temporal UI

```
http://localhost:8080

Navigate to:
- Workflows → Find ClaudeMvpWorkflow
- Activities → See run_claude_agent_activity, create_workspace_directory
- Event History → Full execution trace
```

### Check Traces View (AgentEx UI)

Navigate to traces to see:
- Turn-level spans showing each conversation turn
- Nested subagent spans (e.g., "Subagent: code-reviewer")
- Timing and cost per operation

### Check Redis Streams

```bash
redis-cli
> KEYS stream:*
> XREAD COUNT 10 STREAMS stream:{task_id} 0
```

## Troubleshooting

### "Claude Code CLI not found"

Claude Agents SDK requires the Claude Code CLI. Install:
```bash
npm install -g @anthropic-ai/claude-code
```

### "ANTHROPIC_API_KEY not set"

Set the environment variable:
```bash
export ANTHROPIC_API_KEY="your-key"
```

Or add to `.env.local`:
```
ANTHROPIC_API_KEY=your-key
```

### "Text appears instantly (no character animation)"

**This is expected!** Claude SDK returns complete text blocks, not individual tokens. The streaming infrastructure works correctly - text appears as soon as Claude generates each block.

For character-by-character animation (like OpenAI), would need:
1. Claude SDK to expose token-level streaming API (currently not available)
2. Or client-side animation simulation

### "Workspace not found"

Check:
1. Workspace defaults to `./workspace/` relative to tutorial directory
2. Override with `CLAUDE_WORKSPACE_ROOT` env var if needed
3. Worker has permission to create directories

### "Context not maintained"

Verify:
1. Session resume is working (check logs for "CONTINUED" on turn 2+)
2. `StateModel.claude_session_id` is being stored
3. Activity receives `resume_session_id` parameter

## Future Enhancements

Possible improvements for production use:

- **Automatic Plugin** - Auto-intercept Claude SDK calls (like OpenAI plugin pattern)
- **Error Categorization** - Distinguish retriable vs non-retriable errors
- **Token-Level Streaming** - If Claude SDK adds token streaming API
- **Tests** - Unit and integration test coverage
- **Production Hardening** - Resource limits, security policies, monitoring

## What We Learned

### Key Insights from Building This Integration

1. **ContextInterceptor Pattern** - Reusable across agent SDKs (worked for both OpenAI and Claude)
2. **Session Resume is Critical** - Without it, agents can't maintain context across turns
3. **Tool Result Format Varies** - Claude uses `UserMessage` for tool results (with `permission_mode="acceptEdits"`)
4. **Streaming APIs Differ** - OpenAI provides token deltas, Claude provides message blocks
5. **Subagents are Config** - Not separate processes, just routing within Claude SDK
6. **Temporal Determinism** - File I/O must be in activities, not workflows

### Architecture Wins

- ✅ **70% code reuse** from OpenAI integration (ContextInterceptor, streaming infrastructure)
- ✅ **Clean separation** - AgentEx orchestrates, Claude executes
- ✅ **No SDK forks** - Used standard Claude SDK as-is
- ✅ **Durable execution** - All conversation state preserved in Temporal

## Contributing

Contributions welcome! Areas for improvement:
- Add comprehensive tests
- Implement automatic plugin (intercept Claude SDK calls)
- Error categorization and better error messages
- Additional subagent examples

## License

Same as AgentEx SDK (Apache 2.0)
