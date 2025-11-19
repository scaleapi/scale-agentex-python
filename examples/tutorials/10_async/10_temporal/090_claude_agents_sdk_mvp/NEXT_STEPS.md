# Claude Integration - Next Steps

This document outlines the roadmap from MVP v0 to production-ready Claude Agents SDK integration with AgentEx.

---

## Phase 1: Production-Ready Core (Week 1-2)

### 1.1 Build ClaudeAgentsPlugin 🔴 HIGH PRIORITY

**Current state**: Manual activity wrapping via `workflow.execute_activity()`
**Goal**: Automatic interception of Claude SDK calls

**Effort**: 2-3 days
**Files to create**:
- `src/agentex/lib/core/temporal/plugins/claude_agents/plugin.py`
- `src/agentex/lib/core/temporal/plugins/claude_agents/interceptors.py`

**Implementation**:
```python
class ClaudeAgentsPlugin:
    """Temporal plugin for Claude Agents SDK

    Similar to temporalio.contrib.openai_agents.OpenAIAgentsPlugin
    but for Claude SDK.
    """

    def create_workflow_interceptor(self):
        return ClaudeWorkflowInterceptor(self)

class ClaudeWorkflowInterceptor:
    """Intercepts ClaudeSDKClient.query() and wraps in activity"""

    def execute_activity(self, input):
        # Detect Claude SDK calls
        # Wrap in run_claude_agent_activity
        pass
```

**Benefits**:
- Cleaner workflow code (no manual activity calls)
- Consistent with OpenAI pattern
- Easier to maintain

**Workflow code BEFORE**:
```python
result = await workflow.execute_activity(
    run_claude_agent_activity,
    args=[prompt, workspace, tools],
    ...
)
```

**Workflow code AFTER**:
```python
# Just use Claude SDK naturally!
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt)
    async for message in client.receive_response():
        pass  # Plugin wraps automatically
```

---

### 1.2 Tool Call Streaming 🔴 HIGH PRIORITY

**Current state**: Tool calls execute but aren't visible in UI
**Goal**: Stream tool requests/responses in real-time

**Effort**: 1-2 days
**Files to modify**:
- `src/agentex/lib/core/temporal/plugins/claude_agents/__init__.py`
- Add hooks support

**Implementation**:
```python
# In activity or interceptor
if message contains tool_use:
    # Stream ToolRequestContent
    await adk.streaming.streaming_task_message_context(
        task_id=task_id,
        initial_content=ToolRequestContent(
            author="agent",
            tool_name=tool_name,
            tool_input=tool_input,
        )
    )

if message contains tool_result:
    # Stream ToolResponseContent
    await adk.streaming.streaming_task_message_context(
        task_id=task_id,
        initial_content=ToolResponseContent(
            author="agent",
            tool_name=tool_name,
            tool_output=tool_output,
        )
    )
```

**Benefits**:
- Users see what agent is doing
- Better UX (show "Reading file...", "Writing file...")
- Debugging is easier

---

### 1.3 Error Handling & Categorization 🔴 HIGH PRIORITY

**Current state**: All errors retry
**Goal**: Smart error handling with proper categorization

**Effort**: 1 day
**Files to modify**:
- `src/agentex/lib/core/temporal/plugins/claude_agents/__init__.py`

**Implementation**:
```python
from temporalio.exceptions import ApplicationError
from claude_agent_sdk import CLINotFoundError, RateLimitError

try:
    result = await claude_sdk_call()
except CLINotFoundError as e:
    # Non-retriable - fail immediately with helpful message
    raise ApplicationError(
        "Claude Code CLI not installed. Install: npm install -g @anthropic-ai/claude-code",
        non_retryable=True
    )
except RateLimitError as e:
    # Retriable - let Temporal handle with backoff
    raise  # Temporal retries automatically
except SafetyError as e:
    # Non-retriable - Claude refused for safety
    raise ApplicationError(
        f"Request blocked by Claude safety filters: {e}",
        non_retryable=True
    )
except Exception as e:
    # Unknown error - retry with limits
    raise
```

**Benefits**:
- Faster feedback on non-retriable errors
- Better error messages for users
- Reduced unnecessary API calls

---

## Phase 2: Advanced Features (Week 3-4)

### 2.1 Tracing Wrapper 🟡 MEDIUM PRIORITY

**Current state**: No tracing around Claude calls
**Goal**: Wrap Claude calls in tracing spans

**Effort**: 1 day
**Files to create**:
- `src/agentex/lib/core/temporal/plugins/claude_agents/models/temporal_tracing_model.py`

**Implementation**:
```python
class TemporalTracingModel:
    """Wrapper that adds tracing spans around Claude calls"""

    async def execute(self, prompt):
        trace_id = streaming_trace_id.get()
        parent_span_id = streaming_parent_span_id.get()

        async with tracer.span(
            trace_id=trace_id,
            parent_id=parent_span_id,
            name="claude_model_call",
            input={"prompt": prompt[:100]},
        ) as span:
            result = await base_model.execute(prompt)
            span.output = {"result": result}
            return result
```

**Benefits**:
- Observability in AgentEx traces UI
- Token usage tracking
- Latency monitoring
- Debugging

---

### 2.2 Subagent Support 🟡 MEDIUM PRIORITY

**Current state**: Claude's Task tool is disabled
**Goal**: Subagents spawn child Temporal workflows

**Effort**: 2-3 days
**Files to modify**:
- `src/agentex/lib/core/temporal/plugins/claude_agents/__init__.py`
- Add Task tool interception

**Implementation**:
```python
# Detect Claude's Task tool usage
if tool_name == "Task":
    subagent_type = tool_input["subagent_type"]
    prompt = tool_input["prompt"]

    # Spawn child workflow
    result = await workflow.execute_child_workflow(
        ClaudeMvpWorkflow.on_task_create,
        workflow_type=f"{workflow.info().workflow_type}_subagent",
        id=f"{workflow.info().workflow_id}_subagent_{uuid.uuid4()}",
        parent_close_policy=ParentClosePolicy.TERMINATE,
        args=[{
            "prompt": prompt,
            "workspace": parent_workspace,  # Inherit or isolate?
            "secrets": parent_secrets,
        }],
    )

    return result  # Return to Claude as tool result
```

**Benefits**:
- Recursive agents
- Complex multi-step workflows
- Specialized subagents

**Design decisions**:
- Should subagents share parent workspace? (Probably yes)
- Should subagents inherit secrets? (Probably yes)
- How to show subagent activity in UI? (Nested tasks? Separate?)

---

### 2.3 Hooks Integration 🟡 MEDIUM PRIORITY

**Current state**: No hooks, basic tool detection
**Goal**: Use Claude SDK hooks API (if available)

**Effort**: 1-2 days
**Files to create**:
- `src/agentex/lib/core/temporal/plugins/claude_agents/hooks/hooks.py`

**Check first**: Does Claude SDK support hooks API like OpenAI?

**If yes**:
```python
class TemporalStreamingHooks:
    def on_tool_start(self, tool_name, tool_input):
        # Stream tool request
        pass

    def on_tool_end(self, tool_name, tool_output):
        # Stream tool response
        pass
```

**If no**:
Use `can_use_tool` callback to intercept:
```python
options = ClaudeAgentOptions(
    can_use_tool=async def(tool_name, input_data, context):
        # Log/stream tool usage
        await stream_tool_request(tool_name, input_data)
        return {"behavior": "allow", "updatedInput": input_data}
)
```

**Benefits**:
- Fine-grained lifecycle events
- Audit trail
- Better tool visibility

---

## Phase 3: Production Polish (Week 5-6)

### 3.1 Testing 🔴 HIGH PRIORITY

**Effort**: 2-3 days

**Unit tests**:
```bash
tests/plugins/claude_agents/
├── test_plugin.py           # Plugin initialization
├── test_activity.py         # Activity wrapper
├── test_interceptor.py      # Context threading
└── test_workspace.py        # Workspace management
```

**Integration tests**:
```bash
tests/integration/claude_agents/
├── test_workflow.py         # Full workflow execution
├── test_streaming.py        # Streaming to Redis
└── test_subagents.py        # Child workflows
```

**Test coverage goals**:
- Unit: 80%+
- Integration: Key workflows covered

---

### 3.2 Advanced Streaming 🟢 LOW PRIORITY

**Goal**: Stream more content types

**Reasoning content** (if Claude supports extended thinking):
```python
if message contains reasoning:
    await stream_reasoning_content(...)
```

**Image content**:
```python
if message contains image:
    await stream_image_content(...)
```

**Error content**:
```python
if error:
    await stream_error_content(...)
```

---

### 3.3 Cost Tracking 🟡 MEDIUM PRIORITY

**Goal**: Track Claude API costs per task

**Effort**: 1 day
**Implementation**:
```python
# In activity
result = await claude_sdk_call()

# Extract token usage from result
input_tokens = result.usage.input_tokens
output_tokens = result.usage.output_tokens

# Calculate cost (Claude pricing)
cost_usd = (input_tokens * INPUT_TOKEN_PRICE +
            output_tokens * OUTPUT_TOKEN_PRICE)

# Store in result
return {
    "messages": messages,
    "cost_usd": cost_usd,
    "tokens": {"input": input_tokens, "output": output_tokens}
}

# In workflow - accumulate costs
self.total_cost += result["cost_usd"]
```

**Benefits**:
- Cost visibility
- Budget alerts
- Analytics

---

### 3.4 Workspace Cleanup 🟡 MEDIUM PRIORITY

**Goal**: Proper workspace lifecycle management

**Effort**: 1 day
**Implementation**:
```python
# Option 1: Cleanup in workflow
@workflow.run
async def on_task_create(self, params):
    try:
        # ... workflow logic ...
        pass
    finally:
        # Cleanup workspace
        await workflow.execute_activity(
            cleanup_workspace,
            args=[self._workspace_path],
        )

# Option 2: TTL-based cleanup (cron job)
# Delete workspaces older than 7 days
if workspace_age > 7_days:
    shutil.rmtree(workspace_path)

# Option 3: Quota enforcement
if workspace_size > 10_GB:
    raise QuotaExceededError()
```

**Benefits**:
- Disk space management
- No orphaned workspaces
- Quota enforcement

---

## Phase 4: Advanced Patterns (Future)

### 4.1 Multi-Agent Coordination

- Multiple Claude agents in one task
- Agent-to-agent communication
- Shared state management

### 4.2 MCP Server Management

- Auto-start MCP servers with tasks
- Per-task MCP server isolation
- Lifecycle management

### 4.3 Agent Skills

- Package skills with agents
- Share skills across agents
- Version skills

### 4.4 Structured Outputs

- Validate JSON schema outputs
- Type-safe responses
- Schema evolution

---

## Migration Path

### v0 → v1 (Production-Ready)

**Timeline**: 2-3 weeks
**Priorities**:
1. ClaudeAgentsPlugin (Phase 1.1)
2. Tool streaming (Phase 1.2)
3. Error handling (Phase 1.3)
4. Tests (Phase 3.1)

**Deploy to**: Staging environment

### v1 → v2 (Advanced Features)

**Timeline**: 2-3 weeks
**Priorities**:
1. Tracing (Phase 2.1)
2. Subagents (Phase 2.2)
3. Hooks (Phase 2.3)
4. Cost tracking (Phase 3.3)

**Deploy to**: Production environment

---

## Success Metrics

### v1 (Production-Ready)
- ✅ Plugin architecture complete
- ✅ Tool calls visible in UI
- ✅ Smart error handling
- ✅ >80% test coverage
- ✅ Can deploy to staging

### v2 (Advanced)
- ✅ Subagents work
- ✅ Tracing integrated
- ✅ Cost tracking enabled
- ✅ Running in production
- ✅ >5 production agents using Claude

---

## Questions to Answer

1. **Plugin implementation**: Monkey-patch Claude SDK or wrapper pattern?
2. **Subagent workspaces**: Share parent workspace or isolate?
3. **Hooks API**: Does Claude SDK support hooks? If not, use `can_use_tool`?
4. **Cost tracking**: Store per-task or aggregate?
5. **Workspace cleanup**: Immediate, TTL-based, or manual?

---

## Estimated Total Effort

- **Phase 1 (Production core)**: 4-5 days
- **Phase 2 (Advanced features)**: 4-5 days
- **Phase 3 (Polish)**: 3-4 days
- **Total**: 2-3 weeks to production-ready

---

## How to Contribute

1. Pick a task from Phase 1 (highest priority)
2. Create branch: `feat/claude-{task-name}`
3. Implement with tests
4. Update this doc with progress
5. Submit PR

---

## Resources

- [Claude Agents SDK Docs](https://docs.claude.com/en/api/agent-sdk/python)
- [Temporal Python SDK](https://docs.temporal.io/develop/python)
- [OpenAI Plugin Reference](../../060_open_ai_agents_sdk_hello_world/)
- [AgentEx Streaming Docs](../../../../lib/sdk/fastacp/)

---

## Current Status

**MVP v0**: ✅ Complete
**Phase 1**: 🔴 Not started
**Phase 2**: 🔴 Not started
**Phase 3**: 🔴 Not started

---

*Last updated*: 2025-01-19
*Document owner*: AgentEx team
