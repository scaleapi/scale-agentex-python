# Procurement Agent Demo

A demonstration of long-running, autonomous AI agents using **Temporal** and **AgentEx**. This agent manages construction procurement workflows that can run for months, respond to external events, and escalate to humans when needed.

## What This Demo Shows

This demo illustrates a **procurement manager for building construction** that:

- **Runs for months or years** - Temporal workflows enable truly persistent agents
- **Responds to external events** - Not just human input, but signals from the real world (shipments, inspections, etc.)
- **Escalates to humans when needed** - Waits indefinitely for human decisions on critical issues
- **Learns from experience** - Remembers past human decisions and applies them to similar situations
- **Manages complex state** - Uses a database to track construction schedules and procurement items

### Key Concepts

**Long-Running Workflows**: Thanks to Temporal, the agent can live for months, surviving restarts and failures while maintaining full context.

**External Event Integration**: The agent receives real-world signals (not just user messages) via Temporal signals and takes autonomous actions.

**Human-in-the-Loop**: The agent can pause execution indefinitely (up to 24 hours) while waiting for human approval on critical decisions.

**Learning System**: When a human makes a decision, the agent extracts learnings and applies them to future similar situations.

**State Management**: Uses SQLite to persist construction schedules and procurement item status, providing queryable visibility into current operations without parsing conversation history.

**Automatic Summarization**: When conversation history exceeds token limits (~40k tokens), the agent automatically summarizes older messages while preserving recent context, enabling indefinite conversation length.

## Example Workflow

Here's what happens when items move through the procurement pipeline:

1. **Submittal Approved** → Agent issues purchase order and creates tracking record
2. **Shipment Departed Factory** → Agent ingests ETA and checks for schedule conflicts
3. **Shipment Arrived Site** → Agent notifies team and schedules quality inspection
4. **Inspection Failed** → Agent escalates to human with recommended action
5. **Human Decision** → Agent learns from the decision for next time

## Running the Demo

### Prerequisites

You'll need three terminals running:

1. **AgentEx Backend** (database, Temporal server, etc.)
2. **AgentEx UI** (web interface at localhost:3000)
3. **Procurement Agent** (this demo)

### Step 1: Start AgentEx Backend

From the `scale-agentex` repository:

```bash
make dev
```

This starts all required services (Postgres, Temporal, Redis, etc.) via Docker Compose. Verify everything is healthy:

```bash
# Optional: Use lazydocker for a better view
lzd
```

You should see Temporal UI at: http://localhost:8080

### Step 2: Start AgentEx Web UI

From the `scale-agentex-web` repository:

```bash
make dev
```

The UI will be available at: http://localhost:3000

### Step 3: Run the Procurement Agent

From this directory (`examples/demos/procurement_agent`):

```bash
# Install dependencies
uv sync

# Run the agent
export ENVIRONMENT=development && uv run agentex agents run --manifest manifest.yaml
```

The agent will start and register with the AgentEx backend on port 8000.

### Step 4: Create a Task

Go to http://localhost:3000 and:

1. Create a new task for the `procurement-agent`
2. Send a message like "Hello" to initialize the workflow
3. Note the **Workflow ID** from the Temporal UI at http://localhost:8080

### Step 5: Send Test Events

Now simulate real-world procurement events:

```bash
# Navigate to the scripts directory
cd project/scripts

# Send events (you'll be prompted for the workflow ID)
uv run send_test_events.py

# Or provide the workflow ID directly
uv run send_test_events.py <workflow-id>
```

The script sends a series of events simulating the procurement lifecycle for multiple items:
- Steel Beams (passes inspection)
- HVAC Units (fails inspection - agent escalates)
- Windows (passes inspection)
- Flooring Materials (passes inspection)
- Electrical Panels (fails inspection - agent applies learnings)

### Step 6: Observe the Agent

Watch the agent in action:

1. **AgentEx UI** (http://localhost:3000) - See agent responses and decisions
2. **Temporal UI** (http://localhost:8080) - View workflow execution, signals, and state
3. **Terminal** - Watch agent logs for detailed operation info

When an inspection fails, the agent will:
- Analyze the situation
- Recommend an action
- Wait for your response in the AgentEx UI
- Learn from your decision for future similar situations

## Project Structure

```
procurement_agent/
├── project/
│   ├── acp.py                          # ACP server & event handlers
│   ├── workflow.py                     # Main Temporal workflow logic
│   ├── run_worker.py                   # Temporal worker setup
│   ├── agents/
│   │   ├── procurement_agent.py        # Main AI agent with procurement tools
│   │   ├── extract_learnings_agent.py  # Extracts learnings from human decisions
│   │   └── summarization_agent.py      # Summarizes conversation history
│   ├── activities/
│   │   └── activities.py               # Temporal activities (POs, inspections, schedules)
│   ├── data/
│   │   ├── database.py                 # SQLite operations
│   │   └── procurement.db              # Persistent storage (auto-created)
│   ├── models/
│   │   └── events.py                   # Event type definitions (Pydantic models)
│   ├── scripts/
│   │   └── send_test_events.py         # Event simulation script
│   └── utils/
│       ├── learning_extraction.py      # Utilities for extracting context from conversations
│       └── summarization.py            # Token counting and summarization logic
├── manifest.yaml                       # Agent configuration
├── Dockerfile                          # Container definition
└── pyproject.toml                      # Dependencies (uv)
```

## How It Works

### 1. Event-Driven Architecture

The agent receives events via Temporal signals in `workflow.py`:

```python
@workflow.signal
async def send_event(self, event: str) -> None:
    # Validate and queue the event
    await self.event_queue.put(event)
```

Events are validated against Pydantic models and processed by the AI agent.

### 2. Human-in-the-Loop Pattern

Critical decisions require human approval via the `wait_for_human` tool in `procurement_agent.py`:

```python
@function_tool
async def wait_for_human(recommended_action: str) -> str:
    """
    Pause execution until human provides input.
    Waits up to 24 hours for response.
    """
    await workflow.wait_condition(
        lambda: not workflow_instance.human_queue.empty(),
        timeout=timedelta(hours=24),
    )
    # ... return human response
```

The workflow continues only after receiving human input through the AgentEx UI.

### 3. State Management

Instead of cramming everything into the LLM context window, the agent uses SQLite to manage:

- **Master construction schedule** (delivery dates, buffer days, requirements)
- **Procurement items** (status, ETAs, purchase orders, inspection results)

The database is accessed through Temporal activities with proper error handling and retry policies.

### 4. Learning System

When humans make decisions, the agent extracts learnings in `extract_learnings_agent.py`:

```python
# After human input, extract the learning
extraction_result = await Runner.run(extract_agent, new_context, hooks=hooks)
learning = extraction_result.final_output

# Store in workflow state for future reference
self.human_input_learnings.append(learning)
```

These learnings are passed into the agent's system prompt on subsequent runs.

### 5. Automatic Summarization

For long-running workflows, conversation history can grow unbounded. The agent automatically manages context using intelligent summarization:

```python
# After each turn, check if summarization is needed
if should_summarize(self._state.input_list):
    # Find messages to summarize (preserves last 10 turns, starts after previous summary)
    messages_to_summarize, start_index, end_index = get_messages_to_summarize(
        self._state.input_list,
        last_summary_index
    )

    # Generate summary with dedicated agent
    summary_agent = new_summarization_agent()
    summary_result = await Runner.run(summary_agent, messages_to_summarize, hooks=hooks)

    # Replace summarized portion with compact summary
    self._state.input_list = apply_summary_to_input_list(...)
```

Key features:
- **Token threshold**: Triggers at ~40k tokens to stay within model limits
- **Preserves recent context**: Always keeps last 10 user turns in full detail
- **Never re-summarizes**: Starts after the most recent summary to avoid information loss
- **Dedicated summarization agent**: GPT-4o agent focused on extracting key procurement events, decisions, and current state

This enables workflows to run indefinitely without hitting context limits.

### 6. Error Handling & Retries

The workflow uses Temporal's retry policies for resilient execution:

```python
retry_policy = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,  # Exponential backoff
    maximum_interval=timedelta(seconds=120),
    maximum_attempts=5,
    non_retryable_error_types=[
        "DataCorruptionError",
        "ScheduleNotFoundError",
    ]
)
```

Activities automatically retry on transient failures but fail fast on data corruption.

## Key Features

### Durability
- Workflows survive process restarts, crashes, and deployments
- All state is persisted in Temporal and SQLite
- No context is lost even after months of runtime

### External Event Processing
- Responds to events from external systems (ERP, logistics, QA)
- Validates and processes events asynchronously
- Multiple event types supported (approvals, shipments, inspections)

### Human Escalation
- Automatically escalates critical issues (schedule delays, inspection failures)
- Provides recommended actions to humans
- Waits indefinitely (up to 24 hours) for human response
- Continues workflow after receiving guidance

### Learning & Adaptation
- Extracts patterns from human decisions
- Applies learned rules to similar future situations
- Becomes more autonomous over time
- Human maintains oversight and final authority

### Observability
- Full workflow history in Temporal UI
- Real-time agent responses in AgentEx UI
- Detailed logging for debugging
- Database audit trail for all changes

## Customizing the Demo

### Modify the Construction Schedule

Edit the default schedule in `project/data/database.py`:

```python
DEFAULT_SCHEDULE = {
    "project": {
        "name": "Small Office Renovation",
        "start_date": "2026-02-01",
        "end_date": "2026-05-31"
    },
    "deliveries": [
        {
            "item": "Steel Beams",
            "required_by": "2026-02-15",
            "buffer_days": 5
        },
        # ... add more items
    ]
}
```

### Add New Event Types

1. Define the event in `project/models/events.py`
2. Update event validation in `workflow.py`
3. Teach the agent how to handle it in `procurement_agent.py`
4. Add test events in `project/scripts/send_test_events.py`

### Change Agent Behavior

Modify the agent's instructions in `project/agents/procurement_agent.py`:

```python
def new_procurement_agent(master_construction_schedule: str, human_input_learnings: list) -> Agent:
    instructions = f"""
    You are a procurement agent for a commercial building construction project.

    [Your custom instructions here...]
    """
    # ...
```

### Add New Tools

Create new activities in `project/activities/activities.py` and register them as tools:

```python
@activity.defn(name="my_custom_activity")
async def my_custom_activity(param: str) -> str:
    # ... your logic
    return result

# Register in the agent
tools=[
    openai_agents.workflow.activity_as_tool(
        my_custom_activity,
        start_to_close_timeout=timedelta(minutes=10)
    ),
    # ... other tools
]
```

## Troubleshooting

**Agent not appearing in UI**
- Verify agent is running on port 8000: `lsof -i :8000`
- Check `ENVIRONMENT=development` is set
- Review agent logs for errors

**Events not being received**
- Confirm workflow ID is correct (check Temporal UI)
- Verify Temporal server is running: `docker ps | grep temporal`
- Check that send_test_events.py is using the right workflow ID

**Human escalation timeout**
- The agent waits 24 hours for human input before timing out
- Respond in the AgentEx UI task thread
- Check that your message is being sent to the correct task

**Database errors**
- The database is automatically created at `project/data/procurement.db`
- Delete the file to reset: `rm project/data/procurement.db`
- The agent will recreate it on next run

**Import errors**
- Make sure dependencies are installed: `uv sync`
- Verify you're running from the correct directory
- Check Python version is 3.12+

## What's Next?

This demo shows the foundation for autonomous, long-running agents. Potential applications include:

- **Supply chain management** - Track orders, shipments, and inventory across months
- **Compliance workflows** - Monitor regulatory requirements and schedule audits
- **Customer success** - Proactive outreach based on usage patterns and lifecycle stage
- **Infrastructure management** - React to alerts, coordinate maintenance, escalate outages
- **Financial processes** - Invoice approval workflows, budget tracking, expense management

The key insight: **AI agents don't just answer questions—they can run real-world processes autonomously over time.**

## Learn More

- [AgentEx Documentation](https://agentex.sgp.scale.com/docs/)
- [Temporal Documentation](https://docs.temporal.io/)
- [OpenAI Agents SDK](https://github.com/openai/agents-sdk)

---

**Questions or issues?** Open an issue on the [scale-agentex GitHub repository](https://github.com/scaleapi/scale-agentex).
