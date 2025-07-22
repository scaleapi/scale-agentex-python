# BaseACPServer Test Suite

This directory contains comprehensive tests for the `BaseACPServer` and its implementations (`SyncACP`, `AgenticBaseACP`, and `TemporalACP`).

## Test Structure

The test suite is organized into several categories:

### 1. Core Unit Tests (`test_base_acp_server.py`)
- **TestBaseACPServerInitialization**: Server initialization and setup
- **TestHealthCheckEndpoint**: Health check endpoint functionality
- **TestJSONRPCEndpointCore**: Basic JSON-RPC endpoint functionality
- **TestHandlerRegistration**: Handler registration and management
- **TestBackgroundProcessing**: Background task processing
- **TestErrorHandling**: Basic error handling scenarios

### 2. JSON-RPC Endpoint Tests (`test_json_rpc_endpoints.py`)
- **TestJSONRPCMethodHandling**: Method routing and execution
- **TestJSONRPCParameterValidation**: Parameter parsing and validation
- **TestJSONRPCResponseFormat**: Response formatting compliance
- **TestJSONRPCErrorCodes**: JSON-RPC 2.0 error code compliance
- **TestJSONRPCConcurrency**: Concurrent request handling

### 3. Integration Tests (`test_server_integration.py`)
- **TestServerLifecycle**: Server startup, running, and shutdown
- **TestHTTPClientIntegration**: Real HTTP client interactions
- **TestHandlerExecutionIntegration**: Handler execution in server environment
- **TestServerPerformance**: Performance characteristics

### 4. Implementation Tests (`test_implementations.py`)
- **TestSyncACP**: SyncACP-specific functionality
- **TestAgenticBaseACP**: AgenticBaseACP-specific functionality
- **TestTemporalACP**: TemporalACP-specific functionality
- **TestImplementationComparison**: Differences between implementations
- **TestImplementationErrorHandling**: Implementation-specific error handling

### 5. Error Handling Tests (`test_error_handling.py`)
- **TestMalformedRequestHandling**: Invalid and malformed requests
- **TestHandlerErrorHandling**: Handler-level error scenarios
- **TestServerErrorHandling**: Server-level error handling
- **TestEdgeCases**: Edge cases and boundary conditions

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-asyncio httpx pytest-cov pytest-xdist
```

### Basic Usage

Run all tests:
```bash
python run_tests.py
```

Run specific test categories:
```bash
python run_tests.py --category unit
python run_tests.py --category integration
python run_tests.py --category implementations
python run_tests.py --category error
```

### Advanced Options

Run with coverage:
```bash
python run_tests.py --coverage
```

Run in parallel:
```bash
python run_tests.py --parallel 4
```

Run with increased verbosity:
```bash
python run_tests.py -vv
```

Stop on first failure:
```bash
python run_tests.py --failfast
```

Run only failed tests from last run:
```bash
python run_tests.py --lf
```

### Quick Test Options

For development, use these quick test commands:

```bash
# Quick smoke tests
python run_tests.py smoke

# Quick development tests
python run_tests.py quick

# Performance tests only
python run_tests.py perf
```

### Direct pytest Usage

You can also run tests directly with pytest:

```bash
# Run all tests
pytest

# Run specific test file
pytest test_base_acp_server.py

# Run specific test class
pytest test_base_acp_server.py::TestBaseACPServerInitialization

# Run specific test method
pytest test_base_acp_server.py::TestBaseACPServerInitialization::test_base_acp_server_init

# Run with markers
pytest -m "not slow"
```

## Test Configuration

### Fixtures (`conftest.py`)

The test suite uses several fixtures:

- **`free_port`**: Provides a free port for testing
- **`sample_task`**, **`sample_message`**: Sample data objects
- **`base_acp_server`**, **`sync_acp`**, **`agentic_base_acp`**, **`mock_temporal_acp`**: Server instances
- **`test_server_runner`**: Manages server lifecycle for integration tests
- **`jsonrpc_client_factory`**: Creates JSON-RPC test clients
- **`mock_env_vars`**: Mocked environment variables

### Test Utilities

- **`TestServerRunner`**: Manages server startup/shutdown for integration tests
- **`JSONRPCTestClient`**: Simplified JSON-RPC client for testing
- **`find_free_port()`**: Utility to find available ports

## Test Categories Explained

### Unit Tests
Focus on individual components in isolation:
- Server initialization
- Handler registration
- Basic endpoint functionality
- Parameter validation

### Integration Tests
Test components working together:
- Full server lifecycle
- Real HTTP requests
- Handler execution in server context
- Performance characteristics

### Implementation Tests
Test specific ACP implementations:
- SyncACP behavior
- AgenticBaseACP send_event functionality
- TemporalACP workflow integration
- Implementation differences

### Error Handling Tests
Comprehensive error scenarios:
- Malformed JSON-RPC requests
- Handler exceptions
- Server error recovery
- Edge cases and boundary conditions

## Writing New Tests

### Test Naming Convention
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Async Test Example
```python
@pytest.mark.asyncio
async def test_my_async_functionality(self, base_acp_server):
    # Your async test code here
    result = await some_async_operation()
    assert result is not None
```

### Integration Test Example
```python
@pytest.mark.asyncio
async def test_server_integration(self, base_acp_server, free_port, test_server_runner):
    runner = test_server_runner(base_acp_server, free_port)
    await runner.start()
    
    try:
        # Test server functionality
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{free_port}/healthz")
            assert response.status_code == 200
    finally:
        await runner.stop()
```

### Handler Test Example
```python
@pytest.mark.asyncio
async def test_custom_handler(self, base_acp_server):
    handler_called = False
    
    @base_acp_server.on_task_event_send
    async def test_handler(params: SendEventParams):
        nonlocal handler_called
        handler_called = True
        return {"handled": True}
    
    # Test handler execution
    params = SendEventParams(...)
    result = await base_acp_server._handlers[RPCMethod.EVENT_SEND](params)
    
    assert handler_called is True
    assert result["handled"] is True
```

## Continuous Integration

The test suite is designed to work well in CI environments:

- Tests are isolated and don't interfere with each other
- Ports are dynamically allocated to avoid conflicts
- Background tasks are properly cleaned up
- Timeouts are reasonable for CI environments

### CI Configuration Example

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-asyncio httpx pytest-cov
      - run: cd agentex/sdk/fastacp/tests && python run_tests.py --coverage
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: Tests use dynamic port allocation, but if you see port conflicts, try running tests sequentially:
   ```bash
   python run_tests.py --parallel 1
   ```

2. **Async test failures**: Make sure all async tests are marked with `@pytest.mark.asyncio`

3. **Handler not found errors**: Ensure handlers are properly registered before testing

4. **Timeout issues**: Some tests have built-in delays for background processing. If tests are flaky, increase sleep times in test code.

### Debug Mode

Run tests with maximum verbosity and no capture:
```bash
pytest -vvv -s --tb=long
```

### Memory Issues

If you encounter memory issues with large tests:
```bash
python run_tests.py --markers "not memory_intensive"
```

## Contributing

When adding new tests:

1. Follow the existing test structure and naming conventions
2. Add appropriate docstrings explaining what the test does
3. Use fixtures for common setup
4. Clean up resources properly (especially in integration tests)
5. Add tests to the appropriate category in `run_tests.py`
6. Update this README if adding new test categories or significant functionality 