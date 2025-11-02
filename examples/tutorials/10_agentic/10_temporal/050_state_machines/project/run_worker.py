import asyncio
import os

from agents.mcp import MCPServerStdio
from temporalio.contrib.openai_agents import StatelessMCPServerProvider
from project.workflow import StateMachinesTutorialWorkflow
from agentex.lib.utils.debug import setup_debug_if_enabled
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import stream_lifecycle_content
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters
from datetime import timedelta

environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)

environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)

# Configure MCP servers for the worker
MCP_SERVERS = [
    StatelessMCPServerProvider(
        lambda: MCPServerStdio(
            name="mcp-server-time",
            params={
                "command": "uvx",
                "args": ["mcp-server-time", "--local-timezone", "America/Los_Angeles"],
            },
            client_session_timeout_seconds=120,
        )
    ),
    StatelessMCPServerProvider(
        lambda: MCPServerStdio(
            name="openai-websearch-mcp",
            params={
                "command": "uvx",
                "args": ["openai-websearch-mcp"],
                "env": {
                    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")
                }
            },
            client_session_timeout_seconds=120,
        )
    ),
    StatelessMCPServerProvider(
        lambda: MCPServerStdio(
            name="mcp-server-fetch",
            params={
                "command": "uvx",
                "args": ["mcp-server-fetch"],
            },
            client_session_timeout_seconds=120,
        )
    ),
]


async def main():
    # Setup debug mode if enabled
    setup_debug_if_enabled()

    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    # Create a worker with automatic tracing and MCP servers
    worker = AgentexWorker(
        task_queue=task_queue_name,
        mcp_server_providers=MCP_SERVERS,
        plugins=[
            OpenAIAgentsPlugin(
                model_provider=TemporalStreamingModelProvider(),
                model_params=ModelActivityParameters(
                    start_to_close_timeout=timedelta(seconds=180)  # 3 minutes for activities
                ),
            )
        ],
        interceptors=[ContextInterceptor()],
    )

    await worker.run(
        activities=get_all_activities() + [stream_lifecycle_content],
        workflow=StateMachinesTutorialWorkflow,
    )

if __name__ == "__main__":
    asyncio.run(main()) 