"""Custom Temporal activity that runs the OpenAI agent on the harness surface.

LLM calls are non-deterministic, so they must run inside a Temporal activity
rather than directly in the workflow. This activity runs the OpenAI Agents SDK
via ``Runner.run_streamed``, wraps the result in an ``OpenAITurn``, and pushes
the canonical stream to the task stream via ``UnifiedEmitter.auto_send_turn``.

``auto_send`` (which backs ``auto_send_turn``) is explicitly designed to be
called from inside an activity: it writes streaming side effects to Redis and
returns the accumulated final text + normalized usage.
"""

from __future__ import annotations

from agents import Runner
from pydantic import BaseModel
from temporalio import activity

from project.agent import MODEL_NAME, create_agent
from agentex.lib.utils.logging import make_logger
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.lib.adk.providers._modules.openai_turn import OpenAITurn

logger = make_logger(__name__)

RUN_HARNESS_AGENT_ACTIVITY = "run_harness_openai_agent"


class RunHarnessAgentParams(BaseModel):
    """Parameters for the harness agent activity."""

    task_id: str
    user_message: str
    trace_id: str | None = None
    parent_span_id: str | None = None


class HarnessActivities:
    """Hosts the harness-backed OpenAI agent activity."""

    @activity.defn(name=RUN_HARNESS_AGENT_ACTIVITY)
    async def run_harness_openai_agent(self, params: RunHarnessAgentParams) -> str:
        """Run the agent for one turn and auto-send its output; return final text."""
        logger.info(f"Running harness OpenAI agent for task {params.task_id}")

        agent = create_agent()
        result = Runner.run_streamed(starting_agent=agent, input=params.user_message)
        turn = OpenAITurn(result=result, model=MODEL_NAME)
        emitter = UnifiedEmitter(
            task_id=params.task_id,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
        turn_result = await emitter.auto_send_turn(turn)
        return turn_result.final_text
