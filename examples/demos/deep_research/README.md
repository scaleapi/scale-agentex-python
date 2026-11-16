# Deep Research Multi-Agent System

A multi-agent research system built on AgentEx that demonstrates **orchestrator + subagent communication** using Temporal workflows. An orchestrator agent dispatches specialized research subagents (GitHub, Docs, Slack) in parallel, collects their findings, and synthesizes a comprehensive answer.

## Architecture

```
                    ┌─────────────────────┐
                    │   Orchestrator      │
          User ────▶│   (GPT-5.1)         │
          Query     │   Dispatches &      │
                    │   Synthesizes       │
                    └───┬─────┬─────┬─────┘
                        │     │     │
              ┌─────────┘     │     └─────────┐
              ▼               ▼               ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │  GitHub    │  │   Docs     │  │   Slack    │
     │ Researcher │  │ Researcher │  │ Researcher │
     │ (GPT-4.1  │  │ (GPT-4.1  │  │ (GPT-4.1  │
     │  mini)    │  │  mini)    │  │  mini)    │
     │           │  │           │  │           │
     │ GitHub MCP│  │ Web Search│  │ Slack MCP │
     │ Server    │  │ + Fetcher │  │ Server    │
     └────────────┘  └────────────┘  └────────────┘
```

## Key Patterns Demonstrated

### 1. Multi-Agent Orchestration via ACP
The orchestrator creates child tasks on subagents using `adk.acp.create_task()`, sends queries via `EVENT_SEND`, and waits for `research_complete` callback events.

### 2. Shared Task ID for Unified Output
All subagents write messages to the **orchestrator's task ID** (passed as `source_task_id`), so the user sees all research progress in a single conversation thread.

### 3. Conversation Compaction
Subagents use a batched `Runner.run()` pattern with conversation compaction between batches to stay within Temporal's ~2MB payload limit during long research sessions.

### 4. MCP Server Integration
GitHub and Slack subagents use MCP (Model Context Protocol) servers via `StatelessMCPServerProvider` for tool access.

## Agents

| Agent | Port | Model | Tools |
|-------|------|-------|-------|
| Orchestrator | 8010 | gpt-5.1 | dispatch_github, dispatch_docs, dispatch_slack |
| GitHub Researcher | 8011 | gpt-4.1-mini | GitHub MCP (search_code, etc.) |
| Docs Researcher | 8012 | gpt-4.1-mini | web_search (Tavily), fetch_docs_page |
| Slack Researcher | 8013 | gpt-4.1-mini | Slack MCP (search_messages, etc.) |

## Prerequisites

- [AgentEx CLI](https://agentex.sgp.scale.com/docs/) installed
- OpenAI API key
- GitHub Personal Access Token (for GitHub researcher)
- Tavily API key (for Docs researcher) - get one at https://tavily.com
- Slack Bot Token (for Slack researcher)

## Setup

### 1. Environment Variables

Create a `.env` file in each agent directory with the required keys:

**orchestrator/.env:**
```
OPENAI_API_KEY=your-openai-key
```

**github_researcher/.env:**
```
OPENAI_API_KEY=your-openai-key
GITHUB_PERSONAL_ACCESS_TOKEN=your-github-token
```

**docs_researcher/.env:**
```
OPENAI_API_KEY=your-openai-key
TAVILY_API_KEY=your-tavily-key
```

**slack_researcher/.env:**
```
OPENAI_API_KEY=your-openai-key
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_TEAM_ID=your-slack-team-id
```

### 2. Run All Agents

Start each agent in a separate terminal:

```bash
# Terminal 1 - Orchestrator
cd orchestrator
agentex agents run --manifest manifest.yaml

# Terminal 2 - GitHub Researcher
cd github_researcher
agentex agents run --manifest manifest.yaml

# Terminal 3 - Docs Researcher
cd docs_researcher
agentex agents run --manifest manifest.yaml

# Terminal 4 - Slack Researcher
cd slack_researcher
agentex agents run --manifest manifest.yaml
```

### 3. Test

Open the AgentEx UI and send a research question to the orchestrator agent. You should see:
1. The orchestrator dispatching queries to subagents
2. Each subagent streaming its research progress to the same conversation
3. The orchestrator synthesizing all findings into a final answer

## Customization

### Using Different Research Sources

You can adapt the subagents to search different sources:
- Replace the GitHub MCP server with any other MCP server
- Replace Tavily with your preferred search API
- Replace the Slack MCP with any communication platform's MCP
- Update the system prompts to match your target repositories, docs, and channels

### Adding More Subagents

To add a new research subagent:
1. Copy one of the existing subagent directories
2. Update the manifest.yaml with a new agent name and port
3. Modify the workflow.py system prompt and tools
4. Add a new dispatch tool in the orchestrator's workflow.py

## How Shared Task ID Works

The key pattern that makes all agents write to the same conversation:

1. **Orchestrator** passes its `task_id` as `source_task_id` when creating child tasks
2. **Subagents** extract `parent_task_id = params.task.params.get("source_task_id")`
3. **Subagents** use `message_task_id = parent_task_id or params.task.id` for all `adk.messages.create()` calls and `TemporalStreamingHooks`
4. This means all messages and streamed LLM output appear in the orchestrator's task conversation
