# Multi-Agent Content Assembly Line

A multi-agent system that creates content through a collaborative workflow. Four agents work together: a creator generates content, a critic reviews it against rules, and a formatter outputs the final result, all coordinated by an orchestrator.

## 🏗️ Architecture Overview

```
090_multi_agent_non_temporal/
├── project/                  # All agent code
│   ├── creator.py            # Content generation agent
│   ├── critic.py             # Content review agent  
│   ├── formatter.py          # Content formatting agent
│   ├── orchestrator.py       # Workflow coordination agent
│   ├── models.py             # Pydantic models for type safety
│   └── state_machines/
│       └── content_workflow.py  # State machine definitions
├── creator.yaml              # Creator agent manifest
├── critic.yaml               # Critic agent manifest
├── formatter.yaml            # Formatter agent manifest
├── orchestrator.yaml         # Orchestrator agent manifest
├── Dockerfile                # Single shared Dockerfile
├── pyproject.toml            # Dependencies and project configuration
├── start-agents.sh          # Agent management script
└── README.md                # This file
```

## 📁 File Structure

The system uses a shared build configuration with type-safe interfaces:
- **Single `Dockerfile`** with build arguments for different agents
- **Single `pyproject.toml`** for all dependencies  
- **Agent code** in `project/` directory with clear separation of concerns
- **Individual manifest files** at root level for each agent deployment
- **Shared state machine definitions** for workflow coordination
- **Pydantic models** (`models.py`) for type safety and validation across all agents

### Key Files:
- `project/models.py` - Defines request/response models for type safety
- `project/orchestrator.py` - Workflow coordination and inter-agent communication
- `project/creator.py` - Content generation with revision capabilities
- `project/critic.py` - Content validation against rules
- `project/formatter.py` - Multi-format content transformation
- `project/state_machines/content_workflow.py` - State management for the workflow

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- uv package manager
- OpenAI API key (set `OPENAI_API_KEY` or create `.env` file)

### Running the System

1. **Start all agents**:
   ```bash
   cd examples/tutorials/10_agentic/00_base/090_multi_agent_non_temporal
   ./start-agents.sh start
   ```

2. **Check agent status**:
   ```bash
   ./start-agents.sh status
   ```

3. **Send a test request**:
   ```bash
   ./start-agents.sh test
   ```

4. **Monitor logs**:
   ```bash
   ./start-agents.sh logs
   ```

5. **Stop all agents**:
   ```bash
   ./start-agents.sh stop
   ```

## 🤖 Agent Responsibilities

### **Creator Agent** (Port 8001)
- Generates original content based on user requests
- Revises content based on critic feedback
- Maintains conversation history and iteration tracking

### **Critic Agent** (Port 8002)  
- Reviews content against specified rules
- Provides specific, actionable feedback
- Approves content when all rules are met

### **Formatter Agent** (Port 8003)
- Converts approved content to target formats (HTML, Markdown, JSON, etc.)
- Preserves meaning while applying format-specific conventions
- Supports multiple output formats

### **Orchestrator Agent** (Port 8000)
- Coordinates the entire workflow using state machines
- Manages inter-agent communication
- Tracks progress and handles errors/retries

## 📋 Example Request

Send a JSON request to the orchestrator:

```json
{
  "request": "Write a welcome message for our AI assistant",
  "rules": ["Under 50 words", "Friendly tone", "Include emoji"],
  "target_format": "HTML"
}
```

The system will:
1. **Create** content using the Creator agent
2. **Review** against rules using the Critic agent
3. **Revise** if needed (up to 10 iterations)
4. **Format** final approved content using the Formatter agent

## 🔧 Development

### Type Safety with Pydantic
The tutorial demonstrates proper type safety using Pydantic models:

```python
# Define request structure
class CreatorRequest(BaseModel):
    request: str = Field(..., description="The content creation request")
    current_draft: Optional[str] = Field(default=None, description="Current draft for revision")
    feedback: Optional[List[str]] = Field(default=None, description="Feedback from critic")

# Validate incoming requests
creator_request = CreatorRequest.model_validate(request_data)
```

Benefits:
- **Explicit failures** when required fields are missing
- **Self-documenting** APIs with field descriptions
- **IDE support** with auto-completion and type checking
- **Runtime validation** with clear error messages

### Adding New Agents
1. **Add models** to `project/models.py` for request/response types
2. **Create agent** in `project/new_agent.py` using the FastACP pattern
3. **Add manifest** as `new_agent.yaml` at root level with deployment configuration
4. **Update startup script** in `start-agents.sh` to include the new agent

### Modifying Agents
- **Agent code** is in `project/` directory
- **Shared models** are in `project/models.py` for consistency
- **Dependencies** go in `pyproject.toml`
- **Docker configuration** is shared across all agents

### Deployment
Each agent can be deployed independently using its manifest:
```bash
uv run agentex agents deploy --cluster your-cluster --manifest creator.yaml
```

## 🏗️ Technical Implementation

### Shared Dockerfile
The Dockerfile uses build arguments to run different agents:
```dockerfile
CMD uvicorn project.${AGENT_FILE%.*}:acp --host 0.0.0.0 --port ${PORT:-8000}
```

Manifest files specify which agent to run:
```yaml
build_args:
  AGENT_FILE: creator.py
  PORT: 8001
```

### State Machine Flow
The orchestrator coordinates the workflow through these states:
- `CREATING` → `WAITING_FOR_CREATOR` → `REVIEWING` → `WAITING_FOR_CRITIC` → `FORMATTING` → `COMPLETED`

### Inter-Agent Communication
Agents communicate using AgentEx events:
```python
await adk.acp.send_event(
    agent_name="ab090-creator-agent",
    task_id=task_id,
    content=TextContent(author="agent", content=json.dumps(request_data))
)
```

## 📚 What You'll Learn

This tutorial demonstrates:
- **Multi-agent coordination** using state machines for complex workflows
- **Type-safe communication** with Pydantic models for all request/response data
- **Shared build configuration** for multiple agents in a single deployment
- **AgentEx CLI usage** for development and deployment
- **Inter-agent communication patterns** with proper error handling
- **Scalable agent architecture** with clear separation of concerns
