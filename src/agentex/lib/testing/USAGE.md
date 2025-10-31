# AgentEx Testing Framework

Simplified testing framework for AgentEx agents with real infrastructure.

## Quick Start

```python
from agentex.lib.testing import (
    test_sync_agent,
    test_agentic_agent,
    assert_valid_agent_response,
)

# Sync agent test
def test_my_sync_agent():
    with test_sync_agent(agent_name="my-agent") as test:
        response = test.send_message("Hello!")
        assert_valid_agent_response(response)

# Agentic agent test
import pytest

@pytest.mark.asyncio
async def test_my_agentic_agent():
    async with test_agentic_agent(agent_name="my-agent") as test:
        response = await test.send_event("Hello!", timeout_seconds=15.0)
        assert_valid_agent_response(response)
```

## Prerequisites

1. **AgentEx services running**: `make dev`
2. **Agent registered**: Run any tutorial or register your agent
3. **Know your agent name**: Run `agentex agents list`

## Core Principles

### 1. Explicit Agent Selection (Required)

You **must** specify which agent to test:

```python
# ✅ Good - explicit agent name
with test_sync_agent(agent_name="my-agent") as test:
    ...

# ✅ Good - explicit agent ID
with test_sync_agent(agent_id="abc-123") as test:
    ...

# ❌ Bad - will raise AgentSelectionError
with test_sync_agent() as test:  # No agent specified!
    ...
```

### 2. Different APIs for Different Agent Types

**Sync agents** (immediate response):
```python
def test_sync():
    with test_sync_agent(agent_name="my-agent") as test:
        response = test.send_message("Hello")  # Returns immediately
```

**Agentic agents** (async with polling):
```python
@pytest.mark.asyncio
async def test_agentic():
    async with test_agentic_agent(agent_name="my-agent") as test:
        response = await test.send_event("Hello", timeout_seconds=15.0)
```

## Discovering Agent Names

```bash
# List all agents
$ agentex agents list

# Output shows agent names:
# - my-sync-agent (sync)
# - my-agentic-agent (agentic)
```

Use the name from this output in your tests:
```python
with test_sync_agent(agent_name="my-sync-agent") as test:
    ...
```

## API Reference

### Test Functions

#### `test_sync_agent(*, agent_name=None, agent_id=None)`

Create a test session for sync agents.

**Parameters:**
- `agent_name` (str, optional): Agent name (one of agent_name or agent_id required)
- `agent_id` (str, optional): Agent ID (one of agent_name or agent_id required)

**Returns:** Context manager yielding `SyncAgentTest` instance

**Raises:**
- `AgentSelectionError`: No agent specified or multiple agents match
- `AgentNotFoundError`: No matching agent found

**Example:**
```python
def test_calculator_agent():
    with test_sync_agent(agent_name="calculator") as test:
        response = test.send_message("What is 2 + 2?")
        assert_valid_agent_response(response)
        assert "4" in response.content.lower()
```

#### `test_agentic_agent(*, agent_name=None, agent_id=None)`

Create a test session for agentic agents.

**Parameters:** Same as `test_sync_agent`

**Returns:** Async context manager yielding `AgenticAgentTest` instance

**Example:**
```python
@pytest.mark.asyncio
async def test_research_agent():
    async with test_agentic_agent(agent_name="researcher") as test:
        response = await test.send_event(
            "Research quantum computing",
            timeout_seconds=30.0
        )
        assert_valid_agent_response(response)
```

### Test Session Methods

#### `send_message(content: str) -> TextContent`

Send message to sync agent (returns immediately).

```python
response = test.send_message("Hello!")
```

#### `send_event(content: str, timeout_seconds: float) -> TextContent`

Send event to agentic agent and poll for response.

```python
response = await test.send_event("Hello!", timeout_seconds=15.0)
```

#### `get_conversation_history() -> list[TextContent]`

Get full conversation history.

```python
history = test.get_conversation_history()
assert len(history) >= 2  # At least 1 user + 1 agent message
```

### Assertions

#### `assert_valid_agent_response(response: TextContent)`

Validates response is:
- Not None
- TextContent type
- From 'agent' author
- Has non-empty content

```python
response = test.send_message("Hello")
assert_valid_agent_response(response)
```

#### `assert_agent_response_contains(response: TextContent, expected: str, case_sensitive: bool = False)`

Assert response contains expected text.

```python
response = test.send_message("What's the capital of France?")
assert_agent_response_contains(response, "Paris")

# Case-sensitive check
assert_agent_response_contains(response, "PARIS", case_sensitive=True)
```

#### `assert_conversation_maintains_context(history: list[TextContent], keywords: list[str])`

Assert keywords from early messages appear in later messages (context retention).

```python
test.send_message("My name is Alice")
test.send_message("What's my name?")
history = test.get_conversation_history()
assert_conversation_maintains_context(history, ["Alice"])
```

### Exceptions

#### `AgentSelectionError`

Raised when agent selection is missing or ambiguous.

```python
# Multiple agents exist, none specified
with test_sync_agent() as test:  # Raises AgentSelectionError
    ...

# Exception message tells you available agents:
# Available sync agents:
#   - agent-1
#   - agent-2
# Specify agent with: test_sync_agent(agent_name='your-agent')
```

#### `AgentNotFoundError`

Raised when no matching agent found.

```python
with test_sync_agent(agent_name="nonexistent") as test:
    ...  # Raises AgentNotFoundError
```

#### `AgentTimeoutError`

Raised when agentic agent doesn't respond within timeout.

```python
async with test_agentic_agent(agent_name="slow-agent") as test:
    response = await test.send_event("Hello", timeout_seconds=1.0)
    # Raises AgentTimeoutError if takes >1s
```

## Complete Examples

### Sync Agent: Multi-Turn Conversation

```python
def test_conversation_flow():
    with test_sync_agent(agent_name="chatbot") as test:
        # Turn 1
        response1 = test.send_message("My favorite color is blue")
        assert_valid_agent_response(response1)

        # Turn 2
        response2 = test.send_message("What's my favorite color?")
        assert_agent_response_contains(response2, "blue")

        # Verify context maintained
        history = test.get_conversation_history()
        assert_conversation_maintains_context(history, ["blue"])
```

### Agentic Agent: Complex Task

```python
@pytest.mark.asyncio
async def test_data_analysis():
    async with test_agentic_agent(agent_name="analyst") as test:
        # Submit analysis request
        response = await test.send_event(
            "Analyze sales data for Q4 2024",
            timeout_seconds=30.0
        )

        # Validate response
        assert_valid_agent_response(response)
        assert_agent_response_contains(response, "Q4")

        # Follow-up question
        response2 = await test.send_event(
            "What was the trend?",
            timeout_seconds=15.0
        )
        assert_valid_agent_response(response2)
```

### Error Handling

```python
import pytest
from agentex.lib.testing import (
    test_sync_agent,
    AgentSelectionError,
    AgentNotFoundError,
    AgentTimeoutError,
)

def test_missing_agent():
    with pytest.raises(AgentNotFoundError):
        with test_sync_agent(agent_name="nonexistent") as test:
            pass

def test_no_agent_specified():
    with pytest.raises(AgentSelectionError) as exc_info:
        with test_sync_agent() as test:
            pass

    # Error message contains available agents
    assert "Available sync agents:" in str(exc_info.value)

@pytest.mark.asyncio
async def test_timeout():
    async with test_agentic_agent(agent_name="slow-agent") as test:
        with pytest.raises(AgentTimeoutError):
            await test.send_event("Complex task", timeout_seconds=1.0)
```

## Configuration

Configure via environment variables:

```bash
# Infrastructure
export AGENTEX_BASE_URL="http://localhost:5003"
export AGENTEX_HEALTH_TIMEOUT="5.0"

# Polling (agentic agents)
export AGENTEX_POLL_INTERVAL="1.0"          # Initial interval
export AGENTEX_MAX_POLL_INTERVAL="8.0"     # Max interval
export AGENTEX_POLL_BACKOFF="2.0"          # Backoff multiplier

# Retries
export AGENTEX_API_RETRY_ATTEMPTS="3"
export AGENTEX_API_RETRY_DELAY="0.5"
export AGENTEX_API_RETRY_BACKOFF="2.0"

# Task naming
export AGENTEX_TEST_PREFIX="test"
```

## Tips & Best Practices

### 1. Use Constants for Agent Names

```python
# At top of test file
AGENT_NAME = "my-agent"

def test_one():
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        ...

def test_two():
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        ...
```

### 2. Adjust Timeouts for Complex Tasks

```python
# Quick tasks
response = await test.send_event("Hello", timeout_seconds=10.0)

# Complex analysis
response = await test.send_event(
    "Analyze this dataset...",
    timeout_seconds=60.0  # Longer timeout
)
```

### 3. Test Conversation Context

```python
def test_context_retention():
    with test_sync_agent(agent_name="assistant") as test:
        # Establish context
        test.send_message("I work in finance")
        test.send_message("I use Python daily")

        # Query context
        response = test.send_message("What do I work with?")

        # Verify both pieces of context
        history = test.get_conversation_history()
        assert_conversation_maintains_context(
            history,
            ["finance", "Python"]
        )
```

### 4. Handle Multiple Agents

```python
# Test different agents
def test_calculator():
    with test_sync_agent(agent_name="calculator") as test:
        response = test.send_message("2 + 2")
        assert_agent_response_contains(response, "4")

def test_translator():
    with test_sync_agent(agent_name="translator") as test:
        response = test.send_message("Translate 'hello' to Spanish")
        assert_agent_response_contains(response, "hola")
```

## Troubleshooting

### AgentSelectionError: Multiple agents found

**Problem**: You have multiple agents and didn't specify which one.

**Solution**: Specify agent name explicitly:
```python
with test_sync_agent(agent_name="specific-agent") as test:
    ...
```

### AgentNotFoundError: No sync agents registered

**Problem**: No agents of the correct type are running.

**Solution**:
1. Start an agent: Run a tutorial or your agent
2. Verify it's registered: `agentex agents list`
3. Check the agent type matches (sync vs agentic)

### AgentTimeoutError: Agent did not respond

**Problem**: Agentic agent taking too long to respond.

**Solution**:
1. Increase timeout: `timeout_seconds=30.0`
2. Check agent logs for errors
3. Verify agent worker is running
4. Check Temporal workflow status

### InfrastructureError: AgentEx not available

**Problem**: AgentEx services aren't running.

**Solution**:
```bash
# Start services
make dev

# Verify health
curl http://localhost:5003/healthz
```

## Migration from Old API

### Old (fixtures-based)

```python
# Old: Using fixtures
def test_agent(sync_agent):
    ...

def test_agent(real_agentex_client):
    with sync_agent_test_session(client) as test:
        ...
```

### New (explicit functions)

```python
# New: Explicit agent selection
def test_agent():
    with test_sync_agent(agent_name="my-agent") as test:
        ...
```

### Old (auto-selection)

```python
# Old: Auto-selected first agent
with test_sync_agent() as test:
    ...
```

### New (required selection)

```python
# New: Must specify agent
with test_sync_agent(agent_name="my-agent") as test:
    ...
```

## See Also

- Full tutorials: `examples/tutorials/20_behavior_testing/`
- Agent development: `examples/tutorials/00_sync/` and `examples/tutorials/10_agentic/`
- AgentEx CLI: Run `agentex --help`
