# Tutorial 20.1: Agentic Agent Testing

Learn how to test async agents that use event-driven architecture and require polling.

## What You'll Learn

- How async agent testing differs from sync testing
- Using async context managers for testing
- Configuring timeouts for polling
- Testing event-driven behavior

## Prerequisites

- AgentEx services running (`make dev`)
- An async agent running (Tutorial 10_agentic recommended)
- Understanding of async/await in Python

## Quick Start

Run the tests:
```bash
pytest async_test_agent.py -v
```

## Key Differences from Sync Testing

| Aspect | Sync Testing | Agentic Testing |
|--------|-------------|-----------------|
| Response | Immediate | Requires polling |
| Method | `send_message()` | `send_event()` |
| Context manager | Sync (`with`) | Async (`async with`) |
| Test function | Regular function | `@pytest.mark.asyncio` |
| Timeout | N/A | Configure per request |

## The Agentic Test Helper

```python
import pytest
from agentex.lib.testing import async_test_agent

@pytest.mark.asyncio
async def test_my_agent():
    async with async_test_agent() as test:
        # Send event and wait for response
        response = await test.send_event("Hello!", timeout_seconds=15.0)
        assert response is not None
```

## Understanding Timeouts

Agentic agents process events asynchronously, so you need to:
1. Send the event
2. Poll for the response
3. Wait up to `timeout_seconds`

**Default timeout**: 15 seconds
**Recommended timeout**: 20-30 seconds for complex operations

If the agent doesn't respond within the timeout, you'll get a `RuntimeError` with diagnostic information.

## Testing Patterns

### Basic Response
```python
@pytest.mark.asyncio
async def test_agentic_responds():
    async with async_test_agent() as test:
        response = await test.send_event("Hello!", timeout_seconds=15.0)
        assert_valid_agent_response(response)
```

### Multi-Turn Conversation
```python
@pytest.mark.asyncio
async def test_conversation():
    async with async_test_agent() as test:
        r1 = await test.send_event("My name is Alex", timeout_seconds=15.0)
        r2 = await test.send_event("What's my name?", timeout_seconds=15.0)

        history = await test.get_conversation_history()
        assert len(history) >= 2
```

### Long-Running Operations
```python
@pytest.mark.asyncio
async def test_complex_task():
    async with async_test_agent() as test:
        # Some agents need more time for complex work
        response = await test.send_event(
            "Analyze this data...",
            timeout_seconds=30.0  # Longer timeout
        )
        assert response is not None
```

## Troubleshooting

**TimeoutError**: Agent didn't respond in time
- Increase `timeout_seconds`
- Check agent is running
- Check AgentEx logs for errors

**No async agents available**:
- Run an agentic tutorial agent first
- Check `await client.agents.list()` shows async agents

## Next Steps

- Test your own async agents
- Explore temporal agent testing for workflow-based agents
- Integrate behavior tests into CI/CD
