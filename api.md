# Shared Types

```python
from agentex.types import DeleteResponse
```

# Agents

Types:

```python
from agentex.types import (
    AcpType,
    Agent,
    AgentRpcRequest,
    AgentRpcResponse,
    AgentRpcResult,
    DataDelta,
    TaskMessageContent,
    TaskMessageDelta,
    TaskMessageUpdate,
    TextDelta,
    ToolRequestDelta,
    ToolResponseDelta,
    AgentListResponse,
)
```

Methods:

- <code title="get /agents/{agent_id}">client.agents.<a href="./src/agentex/resources/agents.py">retrieve</a>(agent_id) -> <a href="./src/agentex/types/agent.py">Agent</a></code>
- <code title="get /agents">client.agents.<a href="./src/agentex/resources/agents.py">list</a>(\*\*<a href="src/agentex/types/agent_list_params.py">params</a>) -> <a href="./src/agentex/types/agent_list_response.py">AgentListResponse</a></code>
- <code title="delete /agents/{agent_id}">client.agents.<a href="./src/agentex/resources/agents.py">delete</a>(agent_id) -> <a href="./src/agentex/types/shared/delete_response.py">DeleteResponse</a></code>
- <code title="delete /agents/name/{agent_name}">client.agents.<a href="./src/agentex/resources/agents.py">delete_by_name</a>(agent_name) -> <a href="./src/agentex/types/shared/delete_response.py">DeleteResponse</a></code>
- <code title="get /agents/name/{agent_name}">client.agents.<a href="./src/agentex/resources/agents.py">retrieve_by_name</a>(agent_name) -> <a href="./src/agentex/types/agent.py">Agent</a></code>
- <code title="post /agents/{agent_id}/rpc">client.agents.<a href="./src/agentex/resources/agents.py">rpc</a>(agent_id, \*\*<a href="src/agentex/types/agent_rpc_params.py">params</a>) -> <a href="./src/agentex/types/agent_rpc_response.py">AgentRpcResponse</a></code>
- <code title="post /agents/name/{agent_name}/rpc">client.agents.<a href="./src/agentex/resources/agents.py">rpc_by_name</a>(agent_name, \*\*<a href="src/agentex/types/agent_rpc_by_name_params.py">params</a>) -> <a href="./src/agentex/types/agent_rpc_response.py">AgentRpcResponse</a></code>

# Tasks

Types:

```python
from agentex.types import Task, TaskListResponse
```

Methods:

- <code title="get /tasks/{task_id}">client.tasks.<a href="./src/agentex/resources/tasks.py">retrieve</a>(task_id) -> <a href="./src/agentex/types/task.py">Task</a></code>
- <code title="get /tasks">client.tasks.<a href="./src/agentex/resources/tasks.py">list</a>(\*\*<a href="src/agentex/types/task_list_params.py">params</a>) -> <a href="./src/agentex/types/task_list_response.py">TaskListResponse</a></code>
- <code title="delete /tasks/{task_id}">client.tasks.<a href="./src/agentex/resources/tasks.py">delete</a>(task_id) -> <a href="./src/agentex/types/shared/delete_response.py">DeleteResponse</a></code>
- <code title="delete /tasks/name/{task_name}">client.tasks.<a href="./src/agentex/resources/tasks.py">delete_by_name</a>(task_name) -> <a href="./src/agentex/types/shared/delete_response.py">DeleteResponse</a></code>
- <code title="get /tasks/name/{task_name}">client.tasks.<a href="./src/agentex/resources/tasks.py">retrieve_by_name</a>(task_name) -> <a href="./src/agentex/types/task.py">Task</a></code>
- <code title="get /tasks/{task_id}/stream">client.tasks.<a href="./src/agentex/resources/tasks.py">stream_events</a>(task_id) -> object</code>
- <code title="get /tasks/name/{task_name}/stream">client.tasks.<a href="./src/agentex/resources/tasks.py">stream_events_by_name</a>(task_name) -> object</code>

# Messages

Types:

```python
from agentex.types import (
    DataContent,
    MessageAuthor,
    MessageStyle,
    TaskMessage,
    TextContent,
    ToolRequestContent,
    ToolResponseContent,
    MessageListResponse,
)
```

Methods:

- <code title="post /messages">client.messages.<a href="./src/agentex/resources/messages/messages.py">create</a>(\*\*<a href="src/agentex/types/message_create_params.py">params</a>) -> <a href="./src/agentex/types/task_message.py">TaskMessage</a></code>
- <code title="get /messages/{message_id}">client.messages.<a href="./src/agentex/resources/messages/messages.py">retrieve</a>(message_id) -> <a href="./src/agentex/types/task_message.py">TaskMessage</a></code>
- <code title="put /messages/{message_id}">client.messages.<a href="./src/agentex/resources/messages/messages.py">update</a>(message_id, \*\*<a href="src/agentex/types/message_update_params.py">params</a>) -> <a href="./src/agentex/types/task_message.py">TaskMessage</a></code>
- <code title="get /messages">client.messages.<a href="./src/agentex/resources/messages/messages.py">list</a>(\*\*<a href="src/agentex/types/message_list_params.py">params</a>) -> <a href="./src/agentex/types/message_list_response.py">MessageListResponse</a></code>

## Batch

Types:

```python
from agentex.types.messages import BatchCreateResponse, BatchUpdateResponse
```

Methods:

- <code title="post /messages/batch">client.messages.batch.<a href="./src/agentex/resources/messages/batch.py">create</a>(\*\*<a href="src/agentex/types/messages/batch_create_params.py">params</a>) -> <a href="./src/agentex/types/messages/batch_create_response.py">BatchCreateResponse</a></code>
- <code title="put /messages/batch">client.messages.batch.<a href="./src/agentex/resources/messages/batch.py">update</a>(\*\*<a href="src/agentex/types/messages/batch_update_params.py">params</a>) -> <a href="./src/agentex/types/messages/batch_update_response.py">BatchUpdateResponse</a></code>

# Spans

Types:

```python
from agentex.types import Span, SpanListResponse
```

Methods:

- <code title="post /spans">client.spans.<a href="./src/agentex/resources/spans.py">create</a>(\*\*<a href="src/agentex/types/span_create_params.py">params</a>) -> <a href="./src/agentex/types/span.py">Span</a></code>
- <code title="get /spans/{span_id}">client.spans.<a href="./src/agentex/resources/spans.py">retrieve</a>(span_id) -> <a href="./src/agentex/types/span.py">Span</a></code>
- <code title="patch /spans/{span_id}">client.spans.<a href="./src/agentex/resources/spans.py">update</a>(span_id, \*\*<a href="src/agentex/types/span_update_params.py">params</a>) -> <a href="./src/agentex/types/span.py">Span</a></code>
- <code title="get /spans">client.spans.<a href="./src/agentex/resources/spans.py">list</a>(\*\*<a href="src/agentex/types/span_list_params.py">params</a>) -> <a href="./src/agentex/types/span_list_response.py">SpanListResponse</a></code>

# States

Types:

```python
from agentex.types import State, StateListResponse
```

Methods:

- <code title="post /states">client.states.<a href="./src/agentex/resources/states.py">create</a>(\*\*<a href="src/agentex/types/state_create_params.py">params</a>) -> <a href="./src/agentex/types/state.py">State</a></code>
- <code title="get /states/{state_id}">client.states.<a href="./src/agentex/resources/states.py">retrieve</a>(state_id) -> <a href="./src/agentex/types/state.py">State</a></code>
- <code title="put /states/{state_id}">client.states.<a href="./src/agentex/resources/states.py">update</a>(state_id, \*\*<a href="src/agentex/types/state_update_params.py">params</a>) -> <a href="./src/agentex/types/state.py">State</a></code>
- <code title="get /states">client.states.<a href="./src/agentex/resources/states.py">list</a>(\*\*<a href="src/agentex/types/state_list_params.py">params</a>) -> <a href="./src/agentex/types/state_list_response.py">StateListResponse</a></code>
- <code title="delete /states/{state_id}">client.states.<a href="./src/agentex/resources/states.py">delete</a>(state_id) -> <a href="./src/agentex/types/state.py">State</a></code>

# Events

Types:

```python
from agentex.types import Event, EventListResponse
```

Methods:

- <code title="get /events/{event_id}">client.events.<a href="./src/agentex/resources/events.py">retrieve</a>(event_id) -> <a href="./src/agentex/types/event.py">Event</a></code>
- <code title="get /events">client.events.<a href="./src/agentex/resources/events.py">list</a>(\*\*<a href="src/agentex/types/event_list_params.py">params</a>) -> <a href="./src/agentex/types/event_list_response.py">EventListResponse</a></code>

# Tracker

Types:

```python
from agentex.types import AgentTaskTracker, TrackerListResponse
```

Methods:

- <code title="get /tracker/{tracker_id}">client.tracker.<a href="./src/agentex/resources/tracker.py">retrieve</a>(tracker_id) -> <a href="./src/agentex/types/agent_task_tracker.py">AgentTaskTracker</a></code>
- <code title="put /tracker/{tracker_id}">client.tracker.<a href="./src/agentex/resources/tracker.py">update</a>(tracker_id, \*\*<a href="src/agentex/types/tracker_update_params.py">params</a>) -> <a href="./src/agentex/types/agent_task_tracker.py">AgentTaskTracker</a></code>
- <code title="get /tracker">client.tracker.<a href="./src/agentex/resources/tracker.py">list</a>(\*\*<a href="src/agentex/types/tracker_list_params.py">params</a>) -> <a href="./src/agentex/types/tracker_list_response.py">TrackerListResponse</a></code>
