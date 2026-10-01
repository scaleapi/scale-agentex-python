import asyncio
import os

from agents.mcp import MCPServerStdio
from datetime import timedelta
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters, StatelessMCPServerProvider

from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables

from project.workflow import SlackResearchWorkflow

environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)


async def main():
    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
    slack_team_id = os.environ.get("SLACK_TEAM_ID", "")

    slack_env = {**os.environ, "SLACK_BOT_TOKEN": slack_token}
    if slack_team_id:
        slack_env["SLACK_TEAM_ID"] = slack_team_id

    slack_server = StatelessMCPServerProvider(
        name="SlackServer",
        server_factory=lambda: MCPServerStdio(
            name="SlackServer",
            params={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-slack"],
                "env": slack_env,
            },
        ),
    )

    all_activities = get_all_activities()

    context_interceptor = ContextInterceptor()

    model_params = ModelActivityParameters(
        start_to_close_timeout=timedelta(minutes=10),
    )

    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[
            OpenAIAgentsPlugin(
                model_params=model_params,
                mcp_server_providers=[slack_server],
            ),
        ],
        interceptors=[context_interceptor],
    )

    await worker.run(
        activities=all_activities,
        workflow=SlackResearchWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
