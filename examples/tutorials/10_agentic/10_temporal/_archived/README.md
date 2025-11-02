# Archived Temporal Tutorials

**⚠️ DEPRECATED: These tutorials use outdated patterns and are preserved for historical reference only.**

## Why These Are Archived

These tutorials demonstrate the older `run_agent_streamed_auto_send` pattern which has been superseded by the **OpenAI Agents SDK plugin approach** (see the main temporal tutorials).

### Problems with the Old Pattern

The `run_agent_streamed_auto_send` approach has several limitations:

1. **Complex Serialization Required**
   - Manual serialization of agent state
   - Error-prone and boilerplate-heavy
   - Not necessary with the plugin approach

2. **Non-Configurable**
   - Limited flexibility in how agents are configured
   - Harder to customize behavior
   - Less control over the execution flow

3. **Not Officially Supported by Temporal**
   - The OpenAI Agents SDK plugin is the official integration
   - Better long-term support and updates
   - More aligned with Temporal best practices

4. **Inferior Developer Experience**
   - More code to write and maintain
   - Steeper learning curve
   - More opportunities for bugs

## Modern Approach: OpenAI Agents SDK Plugin

For new projects, use the OpenAI Agents SDK plugin demonstrated in:

- **[010_open_ai_agents_sdk_hello_world](../010_open_ai_agents_sdk_hello_world/)** - Basic integration
- **[020_open_ai_agents_sdk_tools](../020_open_ai_agents_sdk_tools/)** - Tool patterns
- **[030_open_ai_agents_sdk_human_in_the_loop](../030_open_ai_agents_sdk_human_in_the_loop/)** - Human oversight

### Why the Plugin is Better

✅ **Automatic activity wrapping** - No manual serialization needed
✅ **Officially supported** - Built with Temporal team collaboration
✅ **Better DX** - Less boilerplate, clearer code
✅ **More configurable** - Fine-grained control when needed
✅ **Future-proof** - Active development and support

## Archived Tutorials

These tutorials remain available for teams with existing codebases using the old pattern:

### 010_agent_chat
Stateful conversation management using `run_agent_streamed_auto_send`.

**Modern equivalent:** [010_open_ai_agents_sdk_hello_world](../010_open_ai_agents_sdk_hello_world/)

### 020_state_machine
Structured state management with explicit state transitions.

**Modern equivalent:** State management is simpler with the plugin approach - see [010_open_ai_agents_sdk_hello_world](../010_open_ai_agents_sdk_hello_world/)

### 030_custom_activities
Custom Temporal activities with manual agent integration.

**Modern equivalent:** [020_open_ai_agents_sdk_tools](../020_open_ai_agents_sdk_tools/) shows activity patterns with automatic wrapping

### 050_agent_chat_guardrails
Safety and validation patterns with the old approach.

**Modern equivalent:** Guardrails work better with the plugin - integration is cleaner and more maintainable

## Migration Guide

If you're using these patterns in existing code:

### 1. Add the OpenAI Agents SDK Plugin

**In `acp.py`:**
```python
from agentex.lib.plugins.openai_agents import OpenAIAgentsPlugin

acp = FastACP.create(
    config=TemporalACPConfig(
        plugins=[OpenAIAgentsPlugin()]
    )
)
```

**In `run_worker.py`:**
```python
from agentex.lib.plugins.openai_agents import OpenAIAgentsPlugin

worker = AgentexWorker(
    task_queue=task_queue_name,
    plugins=[OpenAIAgentsPlugin()],
)
```

### 2. Replace Agent Calls

**Old pattern:**
```python
result = await adk.providers.openai.run_agent_streamed_auto_send(
    task_id=params.task.id,
    input_list=self._state.input_list,
    # ... complex serialization ...
)
```

**New pattern:**
```python
from agents import Agent, Runner

agent = Agent(
    name="My Agent",
    instructions="You are a helpful assistant"
)

result = await Runner.run(agent, self._state.input_list)
```

### 3. Tools Become Simpler

**Old pattern:** Manual activity wrapping, complex serialization

**New pattern:** Use `activity_as_tool()` - automatic activity creation:

```python
from temporalio.contrib import openai_agents
from datetime import timedelta

tools=[
    openai_agents.workflow.activity_as_tool(
        my_activity,
        start_to_close_timeout=timedelta(seconds=10)
    ),
]
```

See [020_open_ai_agents_sdk_tools](../020_open_ai_agents_sdk_tools/) for complete examples.

## Need Help?

- **For new projects:** Start with [010_open_ai_agents_sdk_hello_world](../010_open_ai_agents_sdk_hello_world/)
- **For migration questions:** These archived tutorials show the old patterns if you need reference
- **For modern patterns:** See the main temporal tutorials (010, 020, 030)

## History

These tutorials were created when `run_agent_streamed_auto_send` was the primary integration method. They represented valuable work at the time and taught important Temporal concepts. The ecosystem has evolved, and the OpenAI Agents SDK plugin is now the recommended approach.

**Archived:** November 2024
**Reason:** Superseded by officially supported OpenAI Agents SDK plugin
**Status:** Reference only - use modern tutorials for new projects
