from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List

from agents import Agent, Runner
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.contrib import openai_agents

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
from project.summarization import (
    should_compact,
    compact_tool_outputs,
    new_summarization_agent,
    apply_summary_to_input_list,
)

from project.activities import web_search, fetch_docs_page

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)

TOOL_TIMEOUT = timedelta(minutes=10)

# Update these URLs to match your own documentation sources
SYSTEM_PROMPT = """You are a documentation research specialist. Search official documentation, DeepWiki pages, and the web to find relevant guides, API references, and explanations.

You have two tools:
1. web_search - Search the web using Tavily for broad queries
2. fetch_docs_page - Fetch and read specific documentation pages

KEY DOCUMENTATION SOURCES:
- Official AgentEx Docs: https://agentex.sgp.scale.com/docs/
- DeepWiki (Platform): https://deepwiki.com/scaleapi/scale-agentex
- DeepWiki (Python SDK): https://deepwiki.com/scaleapi/scale-agentex-python

RULES:
1. Start with web_search to find relevant doc pages
2. Fetch the most relevant pages with fetch_docs_page
3. After 5-6 tool calls, produce your final answer as plain text (no tool call)

GUIDELINES:
- Check both official docs AND DeepWiki - they complement each other
- Track URLs for citations
- If you see a summary of previous research, build on it rather than repeating searches

OUTPUT FORMAT - When done, write your findings with a **Sources** section at the end:

**Findings:**
[Your analysis organized by topic]

**Sources:**
For every piece of information, cite the source URL:
- [Page title](https://full-url) - brief description of what was found"""


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class DocsResearchWorkflow(BaseWorkflow):
    def __init__(self) -> None:
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._research_result: str | None = None
        self._task_id: str | None = None
        self._trace_id: str | None = None
        self._parent_span_id: str | None = None
        self._input_list: List[Dict[str, Any]] = []

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        logger.info("Docs researcher received event: %s", params)
        self._task_id = params.task.id
        self._trace_id = params.task.id
        self._parent_span_id = params.task.id

        payload = self._extract_payload(params)

        parent_task_id = None
        parent_agent_name = None
        if params.task and getattr(params.task, "params", None):
            parent_task_id = params.task.params.get("source_task_id")
            parent_agent_name = params.task.params.get("parent_agent_name")
        if not parent_task_id:
            parent_task_id = payload.get("source_task_id")
        if not parent_agent_name:
            parent_agent_name = payload.get("parent_agent_name")

        # Write messages to the parent task so everything appears in one conversation
        message_task_id = parent_task_id or params.task.id

        query = payload.get("query", payload.get("raw_content", ""))
        if not query:
            await adk.messages.create(
                task_id=message_task_id,
                content=TextContent(author="agent", content="No research query provided."),
            )
            self._complete_task = True
            return

        await adk.messages.create(
            task_id=message_task_id,
            content=TextContent(author="agent", content=f"Starting documentation research for: {query}"),
        )

        self._input_list.append({"role": "user", "content": query})

        # Activity-based tools for web search and docs fetching
        agent = Agent(
            name="DocsResearcher",
            instructions=SYSTEM_PROMPT,
            model="gpt-4.1-mini",
            tools=[
                openai_agents.workflow.activity_as_tool(web_search, start_to_close_timeout=TOOL_TIMEOUT, retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=10), backoff_coefficient=2.0)),
                openai_agents.workflow.activity_as_tool(fetch_docs_page, start_to_close_timeout=TOOL_TIMEOUT, retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=10), backoff_coefficient=2.0)),
            ],
        )

        hooks = TemporalStreamingHooks(task_id=message_task_id, timeout=timedelta(minutes=2))

        TURNS_PER_BATCH = 7
        MAX_BATCHES = 5

        for batch_num in range(MAX_BATCHES):
            try:
                result = await Runner.run(agent, self._input_list, hooks=hooks, max_turns=TURNS_PER_BATCH)
                self._input_list = result.to_input_list()

                if result.final_output:
                    self._research_result = result.final_output
                    break
            except Exception as e:
                error_msg = str(e)
                if "Max turns" in error_msg:
                    logger.warning("Docs batch %d hit max turns, attempting synthesis", batch_num)
                    try:
                        synth_input = self._input_list + [
                            {"role": "user", "content": "Synthesize ALL your findings and provide your final comprehensive answer now."}
                        ]
                        synth_result = await Runner.run(agent, synth_input, max_turns=2)
                        self._research_result = synth_result.final_output or "Research incomplete."
                    except Exception:
                        self._research_result = f"Docs research exceeded turn limits after {batch_num + 1} batches."
                    break
                else:
                    logger.warning("Docs research error in batch %d: %s", batch_num, e)
                    self._research_result = f"Docs research was partially completed but encountered an error: {e}"
                    break

            if should_compact(self._input_list):
                logger.info("Compacting docs conversation after batch %d", batch_num)
                self._input_list = compact_tool_outputs(self._input_list)

                if should_compact(self._input_list):
                    try:
                        summary_agent = new_summarization_agent()
                        summary_result = await Runner.run(summary_agent, self._input_list, max_turns=1)
                        if summary_result.final_output:
                            self._input_list = apply_summary_to_input_list(
                                self._input_list, summary_result.final_output, query
                            )
                    except Exception as se:
                        logger.warning("Summarization failed: %s", se)
        else:
            if not self._research_result:
                self._research_result = "Docs research reached maximum iterations without producing a final result."

        if parent_task_id and parent_agent_name:
            await ActivityHelpers.execute_activity(
                activity_name=ACPActivityName.EVENT_SEND,
                request=EventSendParams(
                    agent_name=parent_agent_name,
                    task_id=parent_task_id,
                    content=TextContent(
                        author="agent",
                        content=json.dumps({
                            "event_type": "research_complete",
                            "source_agent": environment_variables.AGENT_NAME,
                            "child_task_id": params.task.id,
                            "result": self._research_result or "No results found.",
                        }),
                    ),
                ),
                response_type=Event,
                start_to_close_timeout=timedelta(seconds=30),
            )

        self._complete_task = True

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> Dict[str, Any]:
        logger.info("Docs research task created: %s", params)
        self._task_id = params.task.id

        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content="Docs Research agent initialized. Send a research query to begin.",
            ),
        )

        await workflow.wait_condition(lambda: self._complete_task, timeout=None)
        await workflow.wait_condition(lambda: workflow.all_handlers_finished())

        return {"status": "complete", "result": self._research_result}

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
