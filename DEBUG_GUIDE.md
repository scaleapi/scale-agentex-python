# AgentEx Debug Guide

AgentEx now supports built-in debugging for both Temporal workers and ACP servers during local development. This guide explains how to use the debug features.

## Quick Start

The simplest way to debug your agent is to add the `--debug-worker` flag:

```bash
uv run agentex agents run --manifest manifest.yaml --debug-worker
```

This will:
- Start the worker in debug mode
- Automatically find an available debug port (starting from 5678)
- Disable auto-reload to prevent conflicts with the debugger
- Print the debug port for IDE attachment

## Debug Options

### Basic Debug Modes

```bash
# Debug worker only (most common)
uv run agentex agents run --manifest manifest.yaml --debug-worker

# Debug ACP server only
uv run agentex agents run --manifest manifest.yaml --debug-acp

# Debug both worker and ACP
uv run agentex agents run --manifest manifest.yaml --debug
```

### Advanced Options

```bash
# Specify debug port (worker uses this port, ACP uses port+1)
uv run agentex agents run --manifest manifest.yaml --debug-worker --debug-port 5679

# Wait for debugger before starting (useful for debugging startup code)
uv run agentex agents run --manifest manifest.yaml --debug-worker --wait-for-debugger
```

## IDE Setup

### VS Code

1. **Start your agent in debug mode:**
   ```bash
   uv run agentex agents run --manifest manifest.yaml --debug-worker
   ```

2. **Note the debug port from the console output:**
   ```
   🐛 Starting Temporal worker in debug mode
   📡 Debug server will listen on port 5678
   💡 In your IDE: Attach to localhost:5678
   ```

3. **Create a launch configuration** (`.vscode/launch.json`):
   ```json
   {
       "version": "0.2.0",
       "configurations": [
           {
               "name": "Attach to AgentEx Worker",
               "type": "python",
               "request": "attach",
               "connect": {
                   "host": "localhost",
                   "port": 5678
               },
               "pathMappings": [
                   {
                       "localRoot": "${workspaceFolder}",
                       "remoteRoot": "."
                   }
               ]
           }
       ]
   }
   ```

4. **Set breakpoints** in your workflow code

5. **Attach debugger**: Go to Run → Start Debugging → "Attach to AgentEx Worker"

### PyCharm

1. **Start your agent in debug mode:**
   ```bash
   uv run agentex agents run --manifest manifest.yaml --debug-worker --debug-port 5678
   ```

2. **Create Remote Debug Configuration:**
   - Go to Run → Edit Configurations
   - Add new "Python Debug Server"
   - Set Host: `localhost`, Port: `5678`
   - Set path mappings if needed

3. **Set breakpoints** and start the debug session

### Other IDEs

Any IDE that supports Python remote debugging via `debugpy` will work:
- Set up remote debugging to `localhost:5678` (or the port shown in console)
- Use the standard `debugpy` connection protocol

## Debug Workflow

### Typical Debug Session

1. **Set breakpoints** in your workflow code (e.g., `workflow.py`)

2. **Start agent in debug mode:**
   ```bash
   uv run agentex agents run --manifest manifest.yaml --debug-worker
   ```

3. **Attach debugger** from your IDE

4. **Trigger workflow execution** by sending events to your agent

5. **Debug normally** - step through code, inspect variables, etc.

### Debugging Startup Code

If you need to debug code that runs during worker startup:

```bash
uv run agentex agents run --manifest manifest.yaml --debug-worker --wait-for-debugger
```

This will pause the worker until you attach the debugger.

## Debug Architecture

### How It Works

- **Debug Mode Detection**: Templates check for `AGENTEX_DEBUG_ENABLED` environment variable
- **Process Isolation**: Debug mode disables auto-reload to prevent conflicts
- **Port Management**: Automatically finds available ports to prevent conflicts
- **Template Integration**: Debug setup is injected into worker and ACP templates

### Debug Environment Variables

When debug mode is active, these environment variables are set:

- `AGENTEX_DEBUG_ENABLED=true`
- `AGENTEX_DEBUG_PORT=5678` (or detected port)
- `AGENTEX_DEBUG_TYPE=worker|acp`
- `AGENTEX_DEBUG_WAIT_FOR_ATTACH=true|false`

## Troubleshooting

### Common Issues

**Port already in use:**
- The CLI automatically finds available ports starting from your specified port
- If you see port conflicts, try specifying a different base port

**Debugger won't attach:**
- Ensure the agent is running and showing debug server messages
- Check that your IDE is connecting to the correct port
- Verify firewall settings aren't blocking the connection

**Breakpoints not hit:**
- Ensure you're setting breakpoints in the correct file paths
- Check that your IDE's path mappings are configured correctly
- Verify the debugger is attached before triggering the workflow

**Auto-reload conflicts:**
- Debug mode automatically disables auto-reload
- If you see restart loops, ensure you're using the debug flags

### Getting Help

**Check debug server status:**
Look for these messages in the console:
```
🐛 [WORKER] Debug server listening on port 5678
📡 [WORKER] Ready for debugger attachment
```

**Verify debugpy installation:**
```bash
pip install debugpy
```

## Examples

### Debug Worker with Custom Port
```bash
uv run agentex agents run --manifest manifest.yaml --debug-worker --debug-port 9999
```

### Debug Both Processes with Wait
```bash
uv run agentex agents run --manifest manifest.yaml --debug --wait-for-debugger
```

### Multiple Debug Sessions
```bash
# Terminal 1 - Agent A
uv run agentex agents run --manifest agent-a/manifest.yaml --debug-worker --debug-port 5678

# Terminal 2 - Agent B  
uv run agentex agents run --manifest agent-b/manifest.yaml --debug-worker --debug-port 5680
```

## Best Practices

1. **Use worker debug for most scenarios** - workflow logic is usually what you want to debug
2. **Set breakpoints before starting** - easier than finding the right moment after startup
3. **Use wait-for-debugger for startup issues** - prevents code from running before you're ready
4. **Check console output** - debug port and status info is always printed
5. **Close debug sessions properly** - stop the agent with Ctrl+C to clean up debug servers

## Integration with Existing Workflows

The debug functionality is designed to be non-intrusive:
- **No code changes required** in your agent
- **Zero configuration** - works out of the box
- **Compatible with all agent types** - sync, agentic, temporal
- **Development only** - debug code only runs in development mode 