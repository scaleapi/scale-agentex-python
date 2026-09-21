# Temporal + OpenAI Agents SDK Streaming Implementation

## TL;DR

We use Temporal interceptors to add real-time streaming to Redis/UI while maintaining workflow determinism with the STANDARD OpenAI Agents plugin. The key challenge was threading `task_id` (only known at runtime) through a plugin system initialized at startup. We solved this using Temporal's interceptor pattern to inject task_id into activity headers, making it available via context variables in the model.

**What we built**: Real-time streaming of LLM responses to users while preserving Temporal's durability guarantees.

**How**: Interceptors thread task_id → Model reads from context → stream to Redis during activity → return complete response for determinism.

**The win**: NO forked plugin needed - uses standard `temporalio.contrib.openai_agents.OpenAIAgentsPlugin`!

## Table of Contents
1. [Background: How OpenAI Agents SDK Works](#background-how-openai-agents-sdk-works)
2. [How Temporal's OpenAI Plugin Works](#how-temporals-openai-plugin-works)
3. [The Streaming Challenge](#the-streaming-challenge)
4. [Our Streaming Solution](#our-streaming-solution)
5. [Implementation Details](#implementation-details)
6. [Usage](#usage)
7. [Drawbacks and Maintenance](#drawbacks-and-maintenance)

---

## Background: How OpenAI Agents SDK Works

Before diving into Temporal integration, let's understand the basic OpenAI Agents SDK flow:

```python
# Standard OpenAI Agents SDK usage
agent = Agent(
    name="Assistant",
    model="gpt-4",
    instructions="You are a helpful assistant"
)

# Under the hood, this happens:
runner = AgentRunner()
result = await runner.run(agent, "Hello")
# ↓
# runner.run() calls agent.model.get_response()
# ↓
# model.get_response() makes the actual LLM API call to OpenAI
```

The key insight: **`model.get_response()`** is where the actual LLM call happens.

---

## How Temporal's OpenAI Plugin Works

The Temporal plugin intercepts this flow to make LLM calls durable by converting them into Temporal activities. Here's how:

### 1. Plugin Setup and Runner Override

When you create the Temporal plugin and pass it to the worker:

```python
# In _temporal_openai_agents.py (lines ~72-112)
@contextmanager
def set_open_ai_agent_temporal_overrides(model_params):
    # This is the critical line - replaces the default runner!
    set_default_agent_runner(TemporalOpenAIRunner(model_params))
```

### 2. Model Interception Chain

Here's the clever interception that happens:

```
Original OpenAI SDK Flow:
┌─────────┐     ┌──────────────┐     ┌───────────────────┐     ┌────────────┐
│  Agent  │ --> │ Runner.run() │ --> │ Model.get_response│ --> │ OpenAI API │
└─────────┘     └──────────────┘     └───────────────────┘     └────────────┘

Temporal Plugin Flow:
┌─────────┐     ┌────────────────────┐     ┌──────────────────────┐
│  Agent  │ --> │ TemporalRunner.run │ --> │ _TemporalModelStub   │
└─────────┘     └────────────────────┘     │   .get_response()    │
                                            └──────────┬───────────┘
                                                       ↓
                                            ┌──────────────────────┐
                                            │  Temporal Activity   │
                                            │ "invoke_model_activity"│
                                            └──────────┬───────────┘
                                                       ↓
                                            ┌──────────────────────┐     ┌────────────┐
                                            │ Model.get_response() │ --> │ OpenAI API │
                                            └──────────────────────┘     └────────────┘
```

### 3. The Model Stub Trick

The `TemporalOpenAIRunner` replaces the agent's model with `_TemporalModelStub`:

```python
# In _openai_runner.py
def _convert_agent(agent):
    # Replace the model with a stub
    new_agent.model = _TemporalModelStub(
        model_name=agent.model,
        model_params=model_params
    )
    return new_agent
```

### 4. Activity Creation

The `_TemporalModelStub` doesn't call the LLM directly. Instead, it creates a Temporal activity:

```python
# In _temporal_model_stub.py
class _TemporalModelStub:
    async def get_response(self, ...):
        # Instead of calling the LLM, create an activity!
        return await workflow.execute_activity_method(
            ModelActivity.invoke_model_activity,  # ← This becomes visible in Temporal UI
            activity_input,
            ...
        )
```

### 5. Actual LLM Call in Activity

Finally, inside the activity, the real LLM call happens:

```python
# In _invoke_model_activity.py
class ModelActivity:
    async def invoke_model_activity(self, input):
        model = self._model_provider.get_model(input["model_name"])
        # NOW we actually call the LLM
        return await model.get_response(...)  # ← Real OpenAI API call
```

**Summary**: The plugin intercepts at TWO levels:
1. **Runner level**: Replaces default runner with TemporalRunner
2. **Model level**: Replaces agent.model with _TemporalModelStub that creates activities

---

## The Streaming Challenge

### Why Temporal Doesn't Support Streaming by Default

Temporal's philosophy is that activities should be:
- **Idempotent**: Same input → same output
- **Retriable**: Can restart from beginning on failure
- **Deterministic**: Replays produce identical results

Streaming breaks these guarantees:
- If streaming fails halfway, where do you restart?
- How do you replay a stream deterministically?
- Partial responses violate idempotency

### Why We Need Streaming Anyway

For Scale/AgentEx customers, **latency is critical**:
- Time to first token matters more than total generation time
- Users expect to see responses as they're generated
- 10-30 second waits for long responses are unacceptable

Our pragmatic decision: **Accept the tradeoff**. If streaming fails midway, we restart from the beginning. This may cause a brief UX hiccup but enables the streaming experience users expect.

---

## Our Streaming Solution

### The Key Insight: Where We Can Hook In

When we instantiate the OpenAI plugin for Temporal, we can pass in a **model provider**:

```python
plugin = OpenAIAgentsPlugin(
    model_provider=StreamingModelProvider()  # ← This is our hook!
)
```

**IMPORTANT**: This model provider returns the ACTUAL model that makes the LLM call - this is the final layer, NOT the stub. This is where `model.get_response()` actually calls OpenAI's API. By providing our own model here, we can:

1. Make the same OpenAI chat completion call with `stream=True`
2. Capture chunks as they arrive
3. Stream them to Redis
4. Still return the complete response for Temporal

Our `StreamingModel` implementation:
1. **Streams to Redis** using XADD commands
2. **Returns complete response** to maintain Temporal determinism

### The Task ID Problem

Here's the critical issue we had to solve:

```
Timeline of Execution:
═══════════════════════════════════════════════════════════════════
Time T0: Application Startup
    plugin = CustomStreamingOpenAIAgentsPlugin(
        model_provider=StreamingModelProvider()  ← No task_id exists yet!
    )

Time T1: Worker Creation
    worker = Worker(plugins=[plugin])           ← Still no task_id!

Time T2: Worker Starts
    await worker.run()                          ← Still no task_id!

Time T3: Workflow Receives Request
    @workflow.defn
    async def on_task_create(params):
        task_id = params.task.id                ← task_id CREATED HERE! 🎯

Time T4: Model Needs to Stream
    StreamingModel.get_response(...?)           ← Need task_id but how?!
═══════════════════════════════════════════════════════════════════
```

**The problem**: The model provider is configured before we know the task_id, but streaming requires task_id to route to the correct Redis channel.

### Our Solution: Temporal Interceptors + Context Variables

Instead of forking the plugin, we use Temporal's interceptor pattern to thread task_id through the system. This elegant solution uses standard Temporal features and requires NO custom plugin components!

Here's exactly how task_id flows through the interceptor chain:

```
┌──────────────────────────────────────────────────────────────────┐
│                         WORKFLOW EXECUTION                          │
│  self._task_id = params.task.id  <-- Store in instance variable    │
└────────────────────────────┬─────────────────────────────────────┘
                             ↓ workflow.instance()
┌──────────────────────────────────────────────────────────────────┐
│          StreamingWorkflowOutboundInterceptor                       │
│  • Reads _task_id from workflow.instance()                         │
│  • Injects into activity headers                                   │
└────────────────────────────┬─────────────────────────────────────┘
                             ↓ headers["streaming-task-id"]="abc123"
┌──────────────────────────────────────────────────────────────────┐
│              STANDARD Temporal Plugin                               │
│  • Uses standard TemporalRunner (no fork!)                         │
│  • Uses standard TemporalModelStub (no fork!)                      │
│  • Creates standard invoke_model_activity                          │
└────────────────────────────┬─────────────────────────────────────┘
                             ↓ activity with headers
┌──────────────────────────────────────────────────────────────────┐
│         StreamingActivityInboundInterceptor                         │
│  • Extracts task_id from headers                                   │
│  • Sets streaming_task_id ContextVar                               │
└────────────────────────────┬─────────────────────────────────────┘
                             ↓ streaming_task_id.set("abc123")
┌──────────────────────────────────────────────────────────────────┐
│              StreamingModel.get_response()                          │
│  • Reads task_id from streaming_task_id.get()                      │
│  • Streams chunks to Redis channel: "stream:abc123"                │
│  • Returns complete response for Temporal                          │
└──────────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────┐
│                            REDIS                                    │
│  XADD stream:abc123 chunk1, chunk2, chunk3...                      │
└────────────────────────────┬─────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────┐
│                         UI SUBSCRIBER                               │
│  Reads from stream:abc123 and displays real-time updates           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### The Interceptor Approach - Clean and Maintainable

Instead of forking components, we use Temporal's interceptor system. Here's what we built:

### 1. StreamingInterceptor - The Main Component

```python
# streaming_interceptor.py
class StreamingInterceptor(Interceptor):
    """Main interceptor that enables task_id threading."""

    def intercept_activity(self, next):
        # Create activity interceptor to extract headers
        return StreamingActivityInboundInterceptor(next, self._payload_converter)

    def workflow_interceptor_class(self, input):
        # Return workflow interceptor class
        return StreamingWorkflowInboundInterceptor
```

### 2. Task ID Flow - Using Standard Components

Here's EXACTLY how task_id flows through the system without any forked components:

#### Step 1: Workflow stores task_id in instance variable
```python
# workflow.py
self._task_id = params.task.id  # Store in instance variable
result = await Runner.run(agent, input)  # No context needed!
```

#### Step 2: Outbound Interceptor injects task_id into headers
```python
# StreamingWorkflowOutboundInterceptor
def start_activity(self, input):
    workflow_instance = workflow.instance()
    task_id = getattr(workflow_instance, '_task_id', None)
    if task_id and "invoke_model_activity" in str(input.activity):
        input.headers["streaming-task-id"] = self._payload_converter.to_payload(task_id)
```

#### Step 3: Inbound Interceptor extracts from headers and sets context
```python
# StreamingActivityInboundInterceptor
async def execute_activity(self, input):
    if input.headers and "streaming-task-id" in input.headers:
        task_id = self._payload_converter.from_payload(input.headers["streaming-task-id"], str)
        streaming_task_id.set(task_id)  # Set ContextVar!
```

#### Step 4: StreamingModel reads from context variable
```python
# StreamingModel.get_response()
from agentex.lib.core.temporal.plugins.openai_agents.streaming_interceptor import (
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id
)

async def get_response(self, ...):
    # Read from ContextVar - set by interceptor!
    task_id = streaming_task_id.get()
    trace_id = streaming_trace_id.get()
    parent_span_id = streaming_parent_span_id.get()

    if task_id:
        # Open streaming context to Redis
        async with adk.streaming.streaming_task_message_context(
            task_id=task_id,
            ...
        ) as streaming_context:
            # Stream tokens as they arrive
            ...
```

### 3. Worker Configuration - Simply Add the Interceptor

```python
# run_worker.py
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin  # STANDARD!
from agentex.lib.core.temporal.plugins.openai_agents import (
    StreamingInterceptor,
    StreamingModelProvider,
)

# Create the interceptor
interceptor = StreamingInterceptor()

# Use STANDARD plugin with streaming model provider
plugin = OpenAIAgentsPlugin(
    model_provider=StreamingModelProvider(),
    model_params=ModelActivityParameters(...)
)

# Create worker with interceptor
worker = Worker(
    client,
    task_queue="example_tutorial_queue",
    workflows=[ExampleTutorialWorkflow],
    activities=[...],
    interceptors=[interceptor],  # Just add interceptor!
)
```

### 4. The Streaming Model - Where Magic Happens

This is where the actual streaming happens. Our `StreamingModel` is what gets called inside the activity:

```python
# streaming_model.py
class StreamingModel(Model):
    async def get_response(self, ..., task_id=None):
        # 1. Open Redis streaming context with task_id
        async with adk.streaming.streaming_task_message_context(
            task_id=task_id,  # ← This creates Redis channel stream:abc123
            initial_content=TextContent(author="agent", content="")
        ) as streaming_context:

            # 2. Make OpenAI call WITH STREAMING
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,  # ← Enable streaming!
                # ... other params ...
            )

            # 3. Process chunks as they arrive
            full_content = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content

                    # 4. Stream to Redis (UI sees this immediately!)
                    delta = TextDelta(type="text", text_delta=content)
                    update = StreamTaskMessageDelta(
                        parent_task_message=streaming_context.task_message,
                        delta=delta,
                        type="delta"
                    )
                    await streaming_context.stream_update(update)

            # 5. Handle tool calls (sent as complete messages, not streamed)
            if tool_calls:
                for tool_call_data in tool_calls.values():
                    tool_request = ToolRequestContent(
                        author="agent",
                        tool_call_id=tool_call_data["id"],
                        name=tool_call_data["function"]["name"],
                        arguments=json.loads(tool_call_data["function"]["arguments"])
                    )

                    # Tool calls use StreamTaskMessageFull (complete message)
                    async with adk.streaming.streaming_task_message_context(
                        task_id=task_id,
                        initial_content=tool_request
                    ) as tool_context:
                        await tool_context.stream_update(
                            StreamTaskMessageFull(
                                parent_task_message=tool_context.task_message,
                                content=tool_request,
                                type="full"
                            )
                        )

            # 6. Handle reasoning tokens (o1 models)
            if reasoning_content:  # For o1 models
                reasoning = ReasoningContent(
                    author="agent",
                    summary=[reasoning_content],
                    type="reasoning"
                )
                # Stream reasoning as complete message
                await stream_reasoning_update(reasoning)

        # 7. Context auto-closes and saves to DB
        # The streaming_task_message_context:
        #   - Accumulates all chunks
        #   - Saves complete message to database
        #   - Sends DONE signal to Redis

        # 8. Return complete response for Temporal determinism
        return ModelResponse(
            output=output_items,  # Complete response
            usage=usage,
            response_id=completion_id
        )
```

### 5. Redis and AgentEx Streaming Infrastructure

Here's what happens under the hood with AgentEx's streaming system:

#### Redis Implementation Details

1. **Channel Creation**: `stream:{task_id}` - Each task gets its own Redis stream
2. **XADD Commands**: Each chunk is appended using Redis XADD
3. **Message Types**:
   - `StreamTaskMessageDelta`: For text chunks (token by token)
   - `StreamTaskMessageFull`: For complete messages (tool calls, reasoning)
4. **Auto-accumulation**: The streaming context accumulates all chunks
5. **Database Persistence**: Complete message saved to DB when context closes
6. **DONE Signal**: Sent to Redis when streaming completes

#### What Gets Streamed

```python
# Text content - streamed token by token
await streaming_context.stream_update(
    StreamTaskMessageDelta(delta=TextDelta(text_delta=chunk))
)

# Tool calls - sent as complete messages
await streaming_context.stream_update(
    StreamTaskMessageFull(content=ToolRequestContent(...))
)

# Reasoning (o1 models) - sent as complete
await streaming_context.stream_update(
    StreamTaskMessageFull(content=ReasoningContent(...))
)

# Guardrails - sent as complete
await streaming_context.stream_update(
    StreamTaskMessageFull(content=GuardrailContent(...))
)
```

#### UI Subscription

The frontend subscribes to `stream:{task_id}` and receives:
1. Real-time text chunks as they're generated
2. Complete tool calls when they're ready
3. Reasoning summaries for o1 models
4. DONE signal when complete

This decoupling means we can stream anything we want through Redis!

### 6. Workflow Integration

```python
# workflow.py
@workflow.defn
class ExampleWorkflow:
    async def on_task_event_send(self, params):
        # Pass task_id through context
        context = {"task_id": params.task.id}  # ← Critical line!

        runner = get_default_agent_runner()  # Gets our StreamingTemporalRunner
        result = await runner.run(agent, input, context=context)
```

---

## Usage

### Installation

This plugin is included in the agentex-python package. No additional installation needed.

### Basic Setup

```python
from agentex.lib.core.temporal.plugins.openai_agents import (
    CustomStreamingOpenAIAgentsPlugin,
    StreamingModelProvider,
)
from temporalio.contrib.openai_agents import ModelActivityParameters
from temporalio.client import Client
from temporalio.worker import Worker
from datetime import timedelta

# Create streaming model provider
model_provider = StreamingModelProvider()

# Create plugin with streaming support
plugin = CustomStreamingOpenAIAgentsPlugin(
    model_params=ModelActivityParameters(
        start_to_close_timeout=timedelta(seconds=120),
    ),
    model_provider=model_provider,
)

# Use with Temporal client
client = await Client.connect(
    "localhost:7233",
    plugins=[plugin]
)

# Create worker with the plugin
worker = Worker(
    client,
    task_queue="my-task-queue",
    workflows=[MyWorkflow],
)
```

### In Your Workflow

```python
from agents import Agent
from agents.run import get_default_agent_runner

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, params):
        # Create an agent
        agent = Agent(
            name="Assistant",
            instructions="You are a helpful assistant",
            model="gpt-4o",
        )

        # Pass task_id through context for streaming
        context = {"task_id": params.task.id}

        # Run the agent - streaming happens automatically!
        runner = get_default_agent_runner()
        result = await runner.run(
            agent,
            params.event.content,
            context=context  # task_id enables streaming
        )

        return result.final_output
```

### Comparison with Original Temporal Plugin

| Feature | Original Plugin | Streaming Plugin |
|---------|----------------|------------------|
| **Response Time** | Complete response only (10-30s wait) | Real-time streaming (immediate feedback) |
| **User Experience** | No feedback during generation | See response as it's generated |
| **Task ID Support** | Not supported | Runtime extraction and threading |
| **Activity Name** | `invoke_model_activity` | `invoke_model_activity_streaming` |
| **Model Stub** | `_TemporalModelStub` | `StreamingTemporalModelStub` |
| **Runner** | `TemporalOpenAIRunner` | `StreamingTemporalRunner` |
| **Redis Integration** | None | Full streaming via AgentEx ADK |
| **Temporal Determinism** | ✅ Yes | ✅ Yes (returns complete response) |
| **Replay Safety** | ✅ Yes | ✅ Yes (streaming is side-effect only) |

---

## Benefits of the Interceptor Approach

### Major Advantages Over Forking

1. **No Code Duplication**: Uses standard `temporalio.contrib.openai_agents` plugin
   - Automatic compatibility with Temporal updates
   - No risk of divergence from upstream features
   - Zero maintenance of forked code

2. **Clean Architecture**:
   - Interceptors are Temporal's official extension mechanism
   - Clear separation between streaming logic and core plugin
   - Easy to enable/disable streaming by adding/removing interceptor

3. **Simplicity**:
   - Single interceptor handles all task_id threading
   - Uses Python's ContextVar for thread-safe async state
   - No need to understand Temporal plugin internals

### Minimal Limitations

1. **Streaming Semantics** (unchanged):
   - On failure, streaming restarts from beginning (may show duplicate partial content)
   - This is acceptable for user experience

2. **Worker Configuration**:
   - Must register interceptor with worker
   - Workflow must store task_id in instance variable

### Future Improvements

1. **Contribute Back**:
   - This pattern could be contributed to Temporal as an example
   - Shows how to extend plugins without forking

2. **Enhanced Features**:
   - Could add request/response interceptors for other use cases
   - Pattern works for any runtime context threading need

### Alternative Approaches Considered

1. **Workflow-level streaming**: Stream directly from workflow (violates determinism)
2. **Separate streaming service**: Additional infrastructure complexity
3. **Polling pattern**: Poor latency characteristics
4. **WebSockets**: Doesn't integrate with existing AgentEx infrastructure

---

## Key Innovation

The most important innovation is **using interceptors for runtime context threading**. Instead of forking the plugin to pass task_id through custom components, we use Temporal's interceptor system with Python's ContextVar. This allows:

- One plugin instance for all workflows (standard plugin!)
- Dynamic streaming channels per execution
- Clean separation of concerns
- No forked components to maintain
- Thread-safe async context propagation
- Compatible with all Temporal updates

---

## Troubleshooting

**No streaming visible in UI:**
- Ensure task_id is passed in the context: `context = {"task_id": params.task.id}`
- Verify Redis is running and accessible
- Check that the UI is subscribed to the correct task channel

**Import errors:**
- Make sure agentex-python/src is in your Python path
- Install required dependencies: `uv add agentex-sdk openai-agents temporalio`

**Activity not found:**
- Ensure the plugin is registered with both client and worker
- Check that `invoke_model_activity_streaming` is registered

---

## Testing

### Running Tests

The streaming model implementation has comprehensive tests in `tests/test_streaming_model.py` that verify all configurations, tool types, and edge cases.

#### From Repository Root

```bash
# Run all tests
rye run pytest src/agentex/lib/core/temporal/plugins/openai_agents/tests/test_streaming_model.py -v

# Run without parallel execution (more stable)
rye run pytest src/agentex/lib/core/temporal/plugins/openai_agents/tests/test_streaming_model.py -v -n0

# Run specific test
rye run pytest src/agentex/lib/core/temporal/plugins/openai_agents/tests/test_streaming_model.py::TestStreamingModelSettings::test_temperature_setting -v
```

#### From Test Directory

```bash
cd src/agentex/lib/core/temporal/plugins/openai_agents/tests

# Run all tests
rye run pytest test_streaming_model.py -v

# Run without parallel execution (recommended)
rye run pytest test_streaming_model.py -v -n0

# Run specific test class
rye run pytest test_streaming_model.py::TestStreamingModelSettings -v
```

#### Test Coverage

The test suite covers:
- **ModelSettings**: All configuration parameters (temperature, reasoning, truncation, etc.)
- **Tool Types**: Function tools, web search, file search, computer tools, MCP tools, etc.
- **Streaming**: Redis context creation, task ID threading, error handling
- **Edge Cases**: Missing task IDs, multiple computer tools, handoffs

**Note**: Tests run faster without parallel execution (`-n0` flag) and avoid potential state pollution between test workers. All 29 tests pass individually; parallel execution may show 4-6 intermittent failures due to shared mock state.

---

## Conclusion

This implementation uses Temporal interceptors to thread task_id through the standard OpenAI plugin to enable real-time streaming while maintaining workflow determinism. The key innovation is using interceptors with Python's ContextVar to propagate runtime context without forking any Temporal components.

This approach provides the optimal user experience with:
- **Zero code duplication** - uses standard Temporal plugin
- **Minimal maintenance** - only interceptor and streaming model to maintain
- **Clean architecture** - leverages Temporal's official extension mechanism
- **Full compatibility** - works with all Temporal and OpenAI SDK updates

The interceptor pattern demonstrates how to extend Temporal plugins without forking, setting a precedent for future enhancements.