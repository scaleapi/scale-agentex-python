"""ACP (Agent Communication Protocol) handler for Agentex.

This is the API layer — it owns the agent lifecycle and runs the OpenAI Agents
SDK *sandbox* agent for each incoming message, returning the agent's final
answer to the Agentex frontend.

The agent uses the LOCAL sandbox backend (``UnixLocalSandboxClient``), which runs
shell commands on the host (this process/container). The OpenAI Agents SDK runs
its tool-call loop internally via ``Runner.run`` and returns the final output, so
this sync handler returns a single ``TextContent`` rather than streaming tokens.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from agentex.lib import adk
from project.agent import run_agent
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.core.tracing.tracing_processor_manager import (
    add_tracing_processor_config,
)

logger = make_logger(__name__)

# LiteLLM proxy auth: copy LITELLM_API_KEY to OPENAI_API_KEY for OpenAI client
# compatibility, so the same example works behind the Scale LiteLLM gateway.
_litellm_key = os.environ.get("LITELLM_API_KEY")
if _litellm_key and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = _litellm_key

SGP_API_KEY = os.environ.get("SGP_API_KEY", "")
SGP_ACCOUNT_ID = os.environ.get("SGP_ACCOUNT_ID", "")
SGP_CLIENT_BASE_URL = os.environ.get("SGP_CLIENT_BASE_URL", "")

if SGP_API_KEY and SGP_ACCOUNT_ID:
    add_tracing_processor_config(
        SGPTracingProcessorConfig(
            sgp_api_key=SGP_API_KEY,
            sgp_account_id=SGP_ACCOUNT_ID,
            sgp_base_url=SGP_CLIENT_BASE_URL,
        )
    )

acp = FastACP.create(acp_type="sync")


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams,
) -> TaskMessageContent:
    """Handle incoming messages by running the local-sandbox agent."""
    task_id = params.task.id
    user_message = params.content.content
    logger.info(f"Processing message for task {task_id}")

    async with adk.tracing.span(
        trace_id=task_id,
        task_id=task_id,
        name="message",
        input={"message": user_message},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        final_output = await run_agent(user_message)
        if turn_span:
            turn_span.output = {"final_output": final_output}

    return TextContent(author="agent", content=final_output)
