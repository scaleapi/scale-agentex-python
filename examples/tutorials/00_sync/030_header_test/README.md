# Header Test Agent

This agent tests header forwarding from the AgentEx backend to the agent.

## Features

- Receives events with forwarded HTTP headers
- Validates that custom headers (like auth keys) are properly forwarded
- Logs header information for debugging

## Testing

The agent will log:
- ✅ When headers are successfully received
- ⚠️  When expected headers are missing
- ❌ When no headers are forwarded at all

## Expected Headers

The agent looks for:
- `x-test-auth-key`: Test authentication key
- `x-custom-header`: Custom header for testing

All headers starting with `x-` should be forwarded (except security-sensitive ones filtered by the backend).
