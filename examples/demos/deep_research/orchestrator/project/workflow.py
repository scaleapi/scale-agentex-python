from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any, Dict, List

from agents import Agent, Runner, ModelSettings, function_tool
from openai.types.shared import Reasoning
from temporalio import workflow

from agentex.lib import adk
from agentex.lib.types.acp import CreateTaskParams, SendEventParams
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.acp.acp_activities import (
    ACPActivityName,
    EventSendParams,
)
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks import TemporalStreamingHooks
from agentex.lib.utils.logging import make_logger
from agentex.types.event import Event
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables

from project.prompts import ORCHESTRATOR_SYSTEM_PROMPT

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)

# Update these to match your subagent names from their manifest.yaml files
GITHUB_AGENT_NAME = "deep-research-github"
DOCS_AGENT_NAME = "deep-research-docs"
SLACK_AGENT_NAME = "deep-research-slack"


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class ResearchOrchestratorWorkflow(BaseWorkflow):
    """Orchestrates deep research by dispatching GitHub, Docs, and Slack subagents."""

    def __init__(self) -> None:
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._research_result: str | None = None
        self._task_id: str | None = None
        self._trace_id: str | None = None
        self._parent_span_id: str | None = None
        self._agent_id: str | None = None
        self._input_list: List[Dict[str, Any]] = []
        # Stores results from subagents keyed by child_task_id
        self._subagent_results: Dict[str, str] = {}

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        logger.info("Orchestrator received event: %s", params)

        if self._task_id is None:
            self._task_id = params.task.id
        if self._trace_id is None:
            self._trace_id = params.task.id
        if self._parent_span_id is None:
            self._parent_span_id = params.task.id
        if self._agent_id is None and getattr(params, "agent", None):
            self._agent_id = params.agent.id

        payload = self._extract_payload(params)

        # Check if this is a research_complete event from a subagent
        event_type = payload.get("event_type")
        if event_type == "research_complete":
            child_task_id = payload.get("child_task_id", "")
            result = payload.get("result", "")
            source = payload.get("source_agent", "unknown")
            self._subagent_results[child_task_id] = result
            logger.info("Received research result from %s (child: %s)", source, child_task_id)
            return

        # Otherwise, this is a user query
        query = payload.get("query", payload.get("raw_content", ""))
        if not query:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="No research query provided. Please send a question.",
                ),
            )
            return

        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    f"Starting deep research for: {query}\n\n"
                    "I'll dispatch specialized research agents to search GitHub, documentation, and Slack."
                ),
            ),
        )

        self._input_list.append({"role": "user", "content": query})

        # Create dispatch tools that operate within this workflow's context
        dispatch_github = self._make_dispatch_tool(GITHUB_AGENT_NAME, "dispatch_github_researcher",
            "Dispatch the GitHub research agent to search across GitHub repos. "
            "Returns comprehensive findings from code, issues, and PRs.")

        dispatch_docs = self._make_dispatch_tool(DOCS_AGENT_NAME, "dispatch_docs_researcher",
            "Dispatch the Docs research agent to search documentation. "
            "Returns findings from documentation sources.")

        dispatch_slack = self._make_dispatch_tool(SLACK_AGENT_NAME, "dispatch_slack_researcher",
            "Dispatch the Slack research agent to search Slack channels. "
            "Returns findings from team discussions.")

        agent = Agent(
            name="ResearchOrchestrator",
            instructions=ORCHESTRATOR_SYSTEM_PROMPT,
            model="gpt-5.1",
            tools=[dispatch_github, dispatch_docs, dispatch_slack],
            model_settings=ModelSettings(
                reasoning=Reasoning(effort="high", summary="auto"),
            ),
        )

        hooks = TemporalStreamingHooks(task_id=params.task.id, timeout=timedelta(minutes=2))
        result = await Runner.run(agent, self._input_list, hooks=hooks, max_turns=50)

        self._research_result = result.final_output
        self._input_list = result.to_input_list()
        self._complete_task = True

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> Dict[str, Any]:
        logger.info("Research orchestrator task created: %s", params)
        self._task_id = params.task.id
        self._agent_id = params.agent.id

        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    "Deep Research Orchestrator initialized.\n\n"
                    "Send me a question and I'll coordinate research across "
                    "GitHub repos, official documentation, and Slack discussions to give you "
                    "a comprehensive answer."
                ),
            ),
        )

        await workflow.wait_condition(lambda: self._complete_task, timeout=None)
        await workflow.wait_condition(lambda: workflow.all_handlers_finished())

        return {"status": "complete", "result": self._research_result}

    def _make_dispatch_tool(self, agent_name: str, tool_name: str, description: str):
        """Create a @function_tool that dispatches to a subagent via ACP and waits for results."""
        workflow_instance = self

        @function_tool(name_override=tool_name, description_override=description)
        async def dispatch(query: str) -> str:
            """
            Args:
                query: The specific research query for this subagent. Be specific about
                       what to search for - include repo names, class/function names,
                       doc page names, or channel names when possible.
            """
            logger.info("Dispatching %s with query: %s", agent_name, query)

            # Create a child task via ACP activity.
            # Pass source_task_id so the subagent can write messages to our task.
            task = await adk.acp.create_task(
                name=f"{agent_name}-{workflow.uuid4()}",
                agent_name=agent_name,
                params={
                    "source_task_id": workflow_instance._task_id,
                    "parent_agent_name": environment_variables.AGENT_NAME,
                },
            )
            child_task_id = task.id
            logger.info("Created child task %s for %s", child_task_id, agent_name)

            # Send the query as an event to the child agent
            await ActivityHelpers.execute_activity(
                activity_name=ACPActivityName.EVENT_SEND,
                request=EventSendParams(
                    agent_name=agent_name,
                    task_id=child_task_id,
                    content=TextContent(
                        author="user",
                        content=json.dumps({"query": query}),
                    ),
                ),
                response_type=Event,
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Wait for the subagent to send back a completion event
            # The signal handler stores results in _subagent_results by child_task_id
            try:
                await workflow.wait_condition(
                    lambda: child_task_id in workflow_instance._subagent_results,
                    timeout=timedelta(minutes=10),
                )
            except asyncio.TimeoutError:
                return f"Research from {agent_name} timed out after 10 minutes."

            result = workflow_instance._subagent_results.get(child_task_id, "No result received.")
            logger.info("Got result from %s (length: %d)", agent_name, len(result))
            return result

        return dispatch

    def _extract_payload(self, params: SendEventParams) -> dict:
        if params.event.content and hasattr(params.event.content, "content"):
            raw_content = params.event.content.content or ""
        else:
            raw_content = ""
        if isinstance(raw_content, dict):
            return raw_content
        if isinstance(raw_content, str):
            try:
                return json.loads(raw_content)
            except json.JSONDecodeError:
                return {"raw_content": raw_content}
        return {"raw_content": str(raw_content)}
