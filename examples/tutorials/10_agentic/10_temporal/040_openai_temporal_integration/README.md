# OpenAI Temporal Integration Tutorial

This tutorial demonstrates the **Agent Platform Integration** for Agentex that provides a streamlined approach to agent development while maintaining full Agentex infrastructure compatibility.

## Before vs After Comparison

| Aspect | Complex Manual (10_agentic/10_temporal/010_agent_chat) | Simplified Platform (this tutorial) |
|--------|-------------------------------------------------------|--------------------------------------|
| **Lines of code** | 277 lines | ~30 lines |
| **Manual orchestration** | Required | Automatic |
| **Activity definitions** | Manual `@activity.defn` for each operation | Built-in durability |
| **State management** | Manual conversation state tracking | Automatic |
| **Error handling** | Manual try/catch and retry logic | Built-in recovery |
| **ACP integration** | Manual message creation/sending | Automatic via bridge |

## Key Features

### **Reduced Complexity**
- Simplified codebase: from 277 lines to ~30 lines
- Automatic agent execution durability
- Built-in tool call orchestration

### **Infrastructure Compatibility**
- Full ACP protocol compatibility
- Existing deployment configurations work unchanged
- Same authentication and monitoring systems
- Multi-tenant hosting support maintained

### **Platform Extensibility**
- OpenAI Agents SDK integration (implemented)
- Extensible architecture for LangChain, CrewAI
- Strategy pattern for custom frameworks

## Implementation Details

### Workflow Definition
```python
@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At040OpenAITemporalIntegration(OpenAIAgentWorkflow):
    async def create_agent(self) -> Agent:
        return Agent(
            name="Tool-Enabled Assistant",
            model="gpt-4o-mini", 
            instructions="You are a helpful assistant...",
            tools=[],  # Add tools as needed
        )
```

### Worker Setup
```python
worker = AgentexWorker(
    task_queue=environment_variables.WORKFLOW_TASK_QUEUE,
    agent_platform="openai",  # Platform optimization
)
await worker.run(activities=[], workflow=At040OpenAITemporalIntegration)
```

## Technical Architecture

### Durability Features
- Agent executions are automatically temporal activities
- Tool calls include built-in retry mechanisms
- Conversation state persists across workflow restarts

### Performance Features
- Automatic exclusion of unused provider activities
- Direct SDK integration reduces overhead
- Platform-specific worker configuration

### Extensibility
- Strategy pattern for adding new agent platforms
- Consistent workflow interface across platforms
- Full compatibility with existing Agentex infrastructure

## Running the Tutorial

1. **Set environment variables:**
   ```bash
   export WORKFLOW_NAME="at040-openai-temporal-integration"
   export WORKFLOW_TASK_QUEUE="040_openai_temporal_integration_queue"
   export AGENT_NAME="at040-openai-temporal-integration"
   export OPENAI_API_KEY="your-openai-api-key"
   ```

2. **Run the agent:**
   ```bash
   uv run agentex agents run --manifest manifest.yaml
   ```

3. **Test via ACP API:**
   ```bash
   curl -X POST http://localhost:8000/api \
     -H "Content-Type: application/json" \
     -d '{
       "method": "task/create",
       "params": {
         "agent_name": "at040-openai-temporal-integration"
       }
     }'
   ```

## Migration from Manual Approach

To migrate from the manual orchestration pattern (010_agent_chat):

1. **Update workflow inheritance:**
   - Change from: `BaseWorkflow` 
   - Change to: `OpenAIAgentWorkflow`

2. **Replace orchestration code:**
   - Remove: Manual `adk.providers.openai.run_agent_streamed_auto_send()` calls
   - Add: `create_agent()` method implementation

3. **Update worker configuration:**
   - Add: `agent_platform="openai"` parameter to `AgentexWorker`
   - Activities: Use empty list `[]` for automatic optimization

4. **Simplify activity management:**
   - Remove: Custom `@activity.defn` wrapper functions
   - Retain: Core business logic as regular functions

This maintains full compatibility with existing Agentex infrastructure.
