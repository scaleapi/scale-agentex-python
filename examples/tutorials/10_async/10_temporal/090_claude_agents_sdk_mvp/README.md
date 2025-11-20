# Claude Agents SDK MVP - Proof of Concept

## What This Is

Minimal integration proving Claude Agents SDK can run in AgentEx Temporal workflows. This is **v0** - a working proof of concept that demonstrates the core pattern.

## What Works ✅

- ✅ **Claude agent executes in Temporal workflow** - Durable, observable, retriable
- ✅ **File operations isolated to workspace directory** - Each task gets own workspace
- ✅ **Session resume & conversation context** - Claude remembers previous messages
- ✅ **Text streaming to UI** - Real-time token streaming via Redis
- ✅ **Tool call visibility** - Tool cards show Read/Write/Bash operations
- ✅ **Subagent support** - Task tool with nested tracing spans
- ✅ **Visible in Temporal UI as activities** - Full observability of execution
- ✅ **Temporal retry policies work** - Automatic retries on failures

## What's Missing (See "Next Steps")

- ❌ **Automatic plugin** - Manual activity wrapping for now
- ❌ **Tracing wrapper** - No tracing around non-subagent calls
- ❌ **Tests** - No unit or integration tests
- ❌ **Error categorization** - All errors retry (no distinction)
- ⚠️ **UI message ordering** - Frontend reorders text/tool cards (cosmetic issue)

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
- Activities → See run_claude_agent_activity
- Event History → Full execution trace
```

### Check Redis

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

### "Streaming not working"

Check:
1. Redis is running: `redis-cli PING`
2. REDIS_URL is set correctly
3. ContextInterceptor is registered in worker
4. task_id is present in activity logs

### "Workspace not found"

Check:
1. CLAUDE_WORKSPACE_ROOT is set (default: /workspaces)
2. Directory exists and is writable
3. Worker has permission to create directories

## Next Steps

See [NEXT_STEPS.md](./NEXT_STEPS.md) for the roadmap to production-ready integration.

**Quick summary**:
- **Phase 1 (Week 1-2)**: Plugin architecture, tool streaming, error handling
- **Phase 2 (Week 3-4)**: Tracing, subagents, hooks
- **Phase 3 (Week 5-6)**: Tests, polish, production deployment

## Contributing

This is an MVP! Contributions welcome:
- Add tests
- Improve error messages
- Add more examples
- Fix bugs

## License

Same as AgentEx SDK (Apache 2.0)
