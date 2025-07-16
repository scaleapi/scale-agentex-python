# AgentexSDK

Methods:

- <code title="get /">client.<a href="./src/agentex_sdk/_client.py">get_root</a>() -> object</code>

# Echo

Methods:

- <code title="post /echo">client.echo.<a href="./src/agentex_sdk/resources/echo.py">send</a>(\*\*<a href="src/agentex_sdk/types/echo_send_params.py">params</a>) -> object</code>

# Agents

Types:

```python
from agentex_sdk.types import AcpType, Agent, AgentRpcRequest, AgentListResponse
```

Methods:

- <code title="get /agents/{agent_id}">client.agents.<a href="./src/agentex_sdk/resources/agents/agents.py">retrieve</a>(agent_id) -> <a href="./src/agentex_sdk/types/agent.py">Agent</a></code>
- <code title="get /agents">client.agents.<a href="./src/agentex_sdk/resources/agents/agents.py">list</a>(\*\*<a href="src/agentex_sdk/types/agent_list_params.py">params</a>) -> <a href="./src/agentex_sdk/types/agent_list_response.py">AgentListResponse</a></code>
- <code title="delete /agents/{agent_id}">client.agents.<a href="./src/agentex_sdk/resources/agents/agents.py">delete</a>(agent_id) -> <a href="./src/agentex_sdk/types/agent.py">Agent</a></code>
- <code title="post /agents/register">client.agents.<a href="./src/agentex_sdk/resources/agents/agents.py">register</a>(\*\*<a href="src/agentex_sdk/types/agent_register_params.py">params</a>) -> <a href="./src/agentex_sdk/types/agent.py">Agent</a></code>
- <code title="post /agents/{agent_id}/rpc">client.agents.<a href="./src/agentex_sdk/resources/agents/agents.py">rpc</a>(agent_id, \*\*<a href="src/agentex_sdk/types/agent_rpc_params.py">params</a>) -> object</code>

## Name

Methods:

- <code title="get /agents/name/{agent_name}">client.agents.name.<a href="./src/agentex_sdk/resources/agents/name.py">retrieve</a>(agent_name) -> <a href="./src/agentex_sdk/types/agent.py">Agent</a></code>
- <code title="delete /agents/name/{agent_name}">client.agents.name.<a href="./src/agentex_sdk/resources/agents/name.py">delete</a>(agent_name) -> <a href="./src/agentex_sdk/types/agent.py">Agent</a></code>

# Tasks

Types:

```python
from agentex_sdk.types import Task, TaskListResponse
```

Methods:

- <code title="get /tasks/{task_id}">client.tasks.<a href="./src/agentex_sdk/resources/tasks/tasks.py">retrieve</a>(task_id) -> <a href="./src/agentex_sdk/types/task.py">Task</a></code>
- <code title="get /tasks">client.tasks.<a href="./src/agentex_sdk/resources/tasks/tasks.py">list</a>() -> <a href="./src/agentex_sdk/types/task_list_response.py">TaskListResponse</a></code>
- <code title="delete /tasks/{task_id}">client.tasks.<a href="./src/agentex_sdk/resources/tasks/tasks.py">delete</a>(task_id) -> <a href="./src/agentex_sdk/types/task.py">Task</a></code>
- <code title="get /tasks/{task_id}/stream">client.tasks.<a href="./src/agentex_sdk/resources/tasks/tasks.py">stream_events</a>(task_id) -> object</code>

## Name

Methods:

- <code title="get /tasks/name/{task_name}">client.tasks.name.<a href="./src/agentex_sdk/resources/tasks/name.py">retrieve</a>(task_name) -> <a href="./src/agentex_sdk/types/task.py">Task</a></code>
- <code title="delete /tasks/name/{task_name}">client.tasks.name.<a href="./src/agentex_sdk/resources/tasks/name.py">delete</a>(task_name) -> <a href="./src/agentex_sdk/types/task.py">Task</a></code>
- <code title="get /tasks/name/{task_name}/stream">client.tasks.name.<a href="./src/agentex_sdk/resources/tasks/name.py">stream_events</a>(task_name) -> object</code>

# Messages

Types:

```python
from agentex_sdk.types import (
    DataContent,
    MessageAuthor,
    MessageStyle,
    StreamingStatus,
    TaskMessage,
    TextContent,
    ToolRequestContent,
    ToolResponseContent,
    MessageListResponse,
)
```

Methods:

- <code title="post /messages">client.messages.<a href="./src/agentex_sdk/resources/messages/messages.py">create</a>(\*\*<a href="src/agentex_sdk/types/message_create_params.py">params</a>) -> <a href="./src/agentex_sdk/types/task_message.py">TaskMessage</a></code>
- <code title="get /messages/{message_id}">client.messages.<a href="./src/agentex_sdk/resources/messages/messages.py">retrieve</a>(message_id) -> <a href="./src/agentex_sdk/types/task_message.py">TaskMessage</a></code>
- <code title="put /messages/{message_id}">client.messages.<a href="./src/agentex_sdk/resources/messages/messages.py">update</a>(message_id, \*\*<a href="src/agentex_sdk/types/message_update_params.py">params</a>) -> <a href="./src/agentex_sdk/types/task_message.py">TaskMessage</a></code>
- <code title="get /messages">client.messages.<a href="./src/agentex_sdk/resources/messages/messages.py">list</a>(\*\*<a href="src/agentex_sdk/types/message_list_params.py">params</a>) -> <a href="./src/agentex_sdk/types/message_list_response.py">MessageListResponse</a></code>

## Batch

Types:

```python
from agentex_sdk.types.messages import BatchCreateResponse, BatchUpdateResponse
```

Methods:

- <code title="post /messages/batch">client.messages.batch.<a href="./src/agentex_sdk/resources/messages/batch.py">create</a>(\*\*<a href="src/agentex_sdk/types/messages/batch_create_params.py">params</a>) -> <a href="./src/agentex_sdk/types/messages/batch_create_response.py">BatchCreateResponse</a></code>
- <code title="put /messages/batch">client.messages.batch.<a href="./src/agentex_sdk/resources/messages/batch.py">update</a>(\*\*<a href="src/agentex_sdk/types/messages/batch_update_params.py">params</a>) -> <a href="./src/agentex_sdk/types/messages/batch_update_response.py">BatchUpdateResponse</a></code>

# Spans

Types:

```python
from agentex_sdk.types import Span, SpanListResponse
```

Methods:

- <code title="post /spans">client.spans.<a href="./src/agentex_sdk/resources/spans.py">create</a>(\*\*<a href="src/agentex_sdk/types/span_create_params.py">params</a>) -> <a href="./src/agentex_sdk/types/span.py">Span</a></code>
- <code title="get /spans/{span_id}">client.spans.<a href="./src/agentex_sdk/resources/spans.py">retrieve</a>(span_id) -> <a href="./src/agentex_sdk/types/span.py">Span</a></code>
- <code title="patch /spans/{span_id}">client.spans.<a href="./src/agentex_sdk/resources/spans.py">update</a>(span_id, \*\*<a href="src/agentex_sdk/types/span_update_params.py">params</a>) -> <a href="./src/agentex_sdk/types/span.py">Span</a></code>
- <code title="get /spans">client.spans.<a href="./src/agentex_sdk/resources/spans.py">list</a>(\*\*<a href="src/agentex_sdk/types/span_list_params.py">params</a>) -> <a href="./src/agentex_sdk/types/span_list_response.py">SpanListResponse</a></code>

# States

Types:

```python
from agentex_sdk.types import State, StateListResponse
```

Methods:

- <code title="post /states">client.states.<a href="./src/agentex_sdk/resources/states.py">create</a>(\*\*<a href="src/agentex_sdk/types/state_create_params.py">params</a>) -> <a href="./src/agentex_sdk/types/state.py">State</a></code>
- <code title="get /states/{state_id}">client.states.<a href="./src/agentex_sdk/resources/states.py">retrieve</a>(state_id) -> <a href="./src/agentex_sdk/types/state.py">State</a></code>
- <code title="put /states/{state_id}">client.states.<a href="./src/agentex_sdk/resources/states.py">update</a>(state_id, \*\*<a href="src/agentex_sdk/types/state_update_params.py">params</a>) -> <a href="./src/agentex_sdk/types/state.py">State</a></code>
- <code title="get /states">client.states.<a href="./src/agentex_sdk/resources/states.py">list</a>(\*\*<a href="src/agentex_sdk/types/state_list_params.py">params</a>) -> <a href="./src/agentex_sdk/types/state_list_response.py">StateListResponse</a></code>
- <code title="delete /states/{state_id}">client.states.<a href="./src/agentex_sdk/resources/states.py">delete</a>(state_id) -> <a href="./src/agentex_sdk/types/state.py">State</a></code>

# Events

Types:

```python
from agentex_sdk.types import Event, EventListResponse
```

Methods:

- <code title="get /events/{event_id}">client.events.<a href="./src/agentex_sdk/resources/events.py">retrieve</a>(event_id) -> <a href="./src/agentex_sdk/types/event.py">Event</a></code>
- <code title="get /events">client.events.<a href="./src/agentex_sdk/resources/events.py">list</a>(\*\*<a href="src/agentex_sdk/types/event_list_params.py">params</a>) -> <a href="./src/agentex_sdk/types/event_list_response.py">EventListResponse</a></code>

# Tracker

Types:

```python
from agentex_sdk.types import AgentTaskTracker, TrackerListResponse
```

Methods:

- <code title="get /tracker/{tracker_id}">client.tracker.<a href="./src/agentex_sdk/resources/tracker.py">retrieve</a>(tracker_id) -> <a href="./src/agentex_sdk/types/agent_task_tracker.py">AgentTaskTracker</a></code>
- <code title="put /tracker/{tracker_id}">client.tracker.<a href="./src/agentex_sdk/resources/tracker.py">update</a>(tracker_id, \*\*<a href="src/agentex_sdk/types/tracker_update_params.py">params</a>) -> <a href="./src/agentex_sdk/types/agent_task_tracker.py">AgentTaskTracker</a></code>
- <code title="get /tracker">client.tracker.<a href="./src/agentex_sdk/resources/tracker.py">list</a>(\*\*<a href="src/agentex_sdk/types/tracker_list_params.py">params</a>) -> <a href="./src/agentex_sdk/types/tracker_list_response.py">TrackerListResponse</a></code>
