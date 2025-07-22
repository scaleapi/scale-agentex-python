# ab080-batch-events - AgentEx Starter Template

This is a tutorial demonstrating **batch event processing** and the **limitations of the base agentic ACP protocol**.

## 🎯 Tutorial Purpose

This tutorial demonstrates three key concepts:

1. **Events and Cursor Usage**: How to use `adk.events.list_events()` with `last_processed_event_id` to track processing progress
2. **Cursor Committing**: How to "commit" the cursor by updating `last_processed_event_id` in the AgentTaskTracker
3. **Base ACP Limitations**: Real-world limitations when building distributed agents with the basic agentic ACP protocol

## ⚠️ Important Limitations

### **Primary Limitation (Race Conditions)**
The code includes this critical limitation:
```python
# LIMITATION - because this is not atomic, it is possible that two different 
# processes will read the value of READY and then both will try to set it to 
# PROCESSING. The only way to prevent this is locking, which is not supported 
# by the agentex server.
```

**Problem**: Multiple pods can simultaneously check status=READY and both proceed to process events, leading to duplicate work.

### **Additional Distributed System Limitations**

1. **Server Crash Recovery**: If the agent server dies while processing events, there's no clean way to restart processing from where it left off. The status remains "PROCESSING" indefinitely.

2. **Cursor Commit Failures**: If the server fails to commit the cursor (`last_processed_event_id`) after writing a message, retrying will lead to duplicate messages being written for the same events.

3. **No Transactional Guarantees**: There's no way to atomically update both the message store and the cursor position, leading to potential inconsistencies.

4. **Base ACP Protocol Constraints**: These issues cannot be solved with the simple agentic base ACP protocol alone - they require more sophisticated coordination mechanisms.

## 🔧 Solutions

The limitations above highlight why more advanced patterns are needed for production systems:

**Options for Production**:
1. **Database Locking**: Implement your own database locking mechanism and provide the agent with database credentials
2. **Temporal Workflows**: Use Temporal to ensure only one workflow execution processes events at a time (eliminates the need for manual locking)
3. **Message Queues**: Use external queue systems with built-in exactly-once delivery guarantees

## 🎯 Batching Demonstration

Despite the limitations, this tutorial effectively demonstrates **event batching behavior**:

- Events arriving during the 2-second processing delay get queued
- When processing completes, all queued events are processed together in the next batch
- This shows how slow agents can efficiently handle bursts of events

## What You'll Learn

- **Tasks**: A task is a grouping mechanism for related messages. Think of it as a conversation thread or a session.
- **Messages**: Messages are communication objects within a task. They can contain text, data, or instructions.
- **ACP Events**: The agent responds to four main events:
  - `task_received`: When a new task is created
  - `task_message_received`: When a message is sent within a task
  - `task_approved`: When a task is approved
  - `task_canceled`: When a task is canceled

## Running the Agent

1. Run the agent locally:
```bash
agentex agents run --manifest manifest.yaml
```

The agent will start on port 8000 and print messages whenever it receives any of the ACP events.

## What's Inside

This template:
- Sets up a basic ACP server
- Handles each of the required ACP events with simple print statements
- Provides a foundation for building more complex agents

## Next Steps

For more advanced agent development, check out the AgentEx tutorials:

- **Tutorials 00-08**: Learn about building synchronous agents with ACP
- **Tutorials 09-10**: Learn how to use Temporal to power asynchronous agents
  - Tutorial 09: Basic Temporal workflow setup
  - Tutorial 10: Advanced Temporal patterns and best practices

These tutorials will help you understand:
- How to handle long-running tasks
- Implementing state machines
- Managing complex workflows
- Best practices for async agent development

## The Manifest File

The `manifest.yaml` file is your agent's configuration file. It defines:
- How your agent should be built and packaged
- What files are included in your agent's Docker image
- Your agent's name and description
- Local development settings (like the port your agent runs on)

This file is essential for both local development and deployment of your agent.

## Project Structure

```
080_batch_events/
├── project/                  # Your agent's code
│   ├── __init__.py
│   └── acp.py               # ACP server and event handlers
├── Dockerfile               # Container definition
├── manifest.yaml            # Deployment config
└── requirements.txt         # Dependencies
```

## Development

1. **Customize Event Handlers**
   - Modify the handlers in `acp.py` to implement your agent's logic
   - Add your own tools and capabilities
   - Implement custom state management

2. **Add Dependencies**
   - Add required packages to `requirements.txt`
   - Update the manifest with any needed credentials

## Local Development

1. **Install AgentEx**
```bash
cd agentex-py
uv venv
source .venv/bin/activate
uv sync
```

2. **Start the Agentex Server**
```bash
# Navigate to the backend directory
cd agentex

# Start all services using Docker Compose
make dev

# Optional: In a separate terminal, use lazydocker for a better UI (everything should say "healthy")
lzd
```

3. **Run your agent**
```bash
# From this directory
export ENVIRONMENT=development && agentex agents run --manifest manifest.yaml
```

4. **Interact with your agent**

Option 0: CLI (deprecated - to be replaced once a new CLI is implemented - please use the web UI for now!)
```bash
# Submit a task via CLI
agentex tasks submit --agent {{ agent_name }} --task "Your task here"
```

Option 1: Web UI
```bash
# Start the local web interface
cd agentex-web
make dev

# Then open http://localhost:3000 in your browser to chat with your agent
```
## Development Tips

1. **Local Testing**
- Set environment variables in project/.env for any required credentials