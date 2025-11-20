# Tutorial 20.0: Basic Sync Agent Testing

Learn how to write automated tests for sync agents using the AgentEx testing framework.

## What You'll Build

Automated tests for sync agents that verify:
- Basic response capability
- Multi-turn conversation
- Context maintenance
- Response content validation

## Prerequisites

- AgentEx services running (`make dev`)
- A sync agent running (Tutorial 00_sync/000_hello_acp recommended)

## Quick Start

Run the tests:
```bash
pytest sync_test_agent.py -v
```

## Understanding Sync Agent Testing

Sync agents respond **immediately** via the `send_message()` API. Testing them is straightforward:

```python
from agentex.lib.testing import sync_test_agent

def test_basic_response():
    with sync_test_agent() as test:
        response = test.send_message("Hello!")
        assert response is not None
```

## The Test Helper: `sync_test_agent()`

The `sync_test_agent()` context manager:
1. Connects to AgentEx
2. Finds a sync agent
3. Creates a test task
4. Returns a `SyncAgentTest` helper
5. Automatically cleans up the task when done

## Key Methods

### `send_message(content: str) -> TextContent`
Send a message and get immediate response (no async/await).

### `get_conversation_history() -> list[TextContent]`
Get all messages exchanged in the test session.

## Common Assertions

```python
from agentex.lib.testing import (
    assert_valid_agent_response,
    assert_agent_response_contains,
    assert_conversation_maintains_context,
)

# Response is valid
assert_valid_agent_response(response)

# Response contains specific text
assert_agent_response_contains(response, "hello")

# Agent maintains context
test.send_message("My name is Alice")
test.send_message("What's my name?")
history = test.get_conversation_history()
assert_conversation_maintains_context(history, ["Alice"])
```

## Test Pattern

A typical sync agent test follows this pattern:

1. **Setup** - `with sync_test_agent() as test:`
2. **Action** - `response = test.send_message("...")`
3. **Assert** - Validate response
4. **Cleanup** - Automatic when context manager exits

## Tips

- Tests skip gracefully if AgentEx isn't running
- Each test gets a fresh task (isolated)
- Conversation history tracks all exchanges
- Use descriptive test names that explain what behavior you're testing

## Next Steps

- Complete Tutorial 20.1 for async agent testing
- Apply these patterns to test your own agents
- Integrate tests into your development workflow
