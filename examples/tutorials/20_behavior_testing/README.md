# Tutorial 20: Agent Behavior Testing

Learn how to write automated tests for your AgentEx agents using the `agentex.lib.testing` framework.

## What You'll Learn

- How to test sync agents with immediate responses
- How to test async agents with event-driven polling
- Writing assertions for agent behavior
- Testing conversation context and multi-turn interactions

## Prerequisites

- AgentEx services running (`make dev` in agentex monorepo)
- At least one agent running (complete Tutorial 00 or Tutorial 10)
- Basic understanding of pytest

## Tutorial Structure

### `000_basic_sync_testing/`
Learn the fundamentals of testing sync agents that respond immediately.

**Key Concepts:**
- Using `sync_test_agent()` context manager
- Sending messages with `send_message()`
- Basic response assertions
- Testing conversation history

**Run:**
```bash
cd 000_basic_sync_testing
pytest sync_test_agent.py -v
```

### `010_agentic_testing/`
Learn how to test async agents that use event-driven architecture.

**Key Concepts:**
- Using `async_test_agent()` async context manager
- Sending events with `send_event()`
- Polling and timeout configuration
- Testing async agent behavior

**Run:**
```bash
cd 010_agentic_testing
pytest async_test_agent.py -v
```

## Quick Start

The simplest way to test an agent:

```python
from agentex.lib.testing import sync_test_agent, assert_valid_agent_response

def test_my_sync_agent():
    with sync_test_agent() as test:
        response = test.send_message("Hello!")
        assert_valid_agent_response(response)
```

For async agents:

```python
import pytest
from agentex.lib.testing import async_test_agent, assert_valid_agent_response

@pytest.mark.asyncio
async def test_my_agentic_agent():
    async with async_test_agent() as test:
        response = await test.send_event("Hello!", timeout_seconds=15.0)
        assert_valid_agent_response(response)
```

## Configuration

Set environment variables to customize behavior:

```bash
export AGENTEX_BASE_URL=http://localhost:5003  # AgentEx server URL
export AGENTEX_TIMEOUT=2.0                      # Health check timeout
```

## Key Design Principles

1. **Real Infrastructure Testing** - Tests run against actual AgentEx, not mocks
2. **Type-Specific Behavior** - Sync and async agents tested differently to match their actual behavior
3. **Graceful Degradation** - Tests skip if AgentEx unavailable
4. **Automatic Cleanup** - Tasks and resources cleaned up after each test

## Next Steps

After completing this tutorial:
- Apply testing to your own agents
- Integrate into CI/CD pipelines
- Write comprehensive test suites for production agents
