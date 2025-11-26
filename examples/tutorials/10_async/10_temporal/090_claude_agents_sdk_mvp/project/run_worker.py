"""Claude MVP Worker - Minimal setup

This worker demonstrates the minimal setup needed to run Claude agents
in AgentEx's Temporal architecture.

Key components:
- ClaudeSDKClient activity (run_claude_agent_activity)
- ContextInterceptor (reused from OpenAI - threads task_id)
- Standard AgentEx activities (messages, streaming, tracing)
"""

import os
import asyncio

# Import workflow
from project.workflow import ClaudeMvpWorkflow

from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker

# Import Claude components
from agentex.lib.core.temporal.plugins.claude_agents import (
    ContextInterceptor,  # Reuse from OpenAI!
    run_claude_agent_activity,
    create_workspace_directory,
)

logger = make_logger(__name__)


async def main():
    """Start the Claude MVP worker"""

    environment_variables = EnvironmentVariables.refresh()

    logger.info("=" * 80)
    logger.info("CLAUDE MVP WORKER STARTING")
    logger.info("=" * 80)
    logger.info(f"Workflow: {environment_variables.WORKFLOW_NAME}")
    logger.info(f"Task Queue: {environment_variables.WORKFLOW_TASK_QUEUE}")
    logger.info(f"Temporal Address: {environment_variables.TEMPORAL_ADDRESS}")
    logger.info(f"Redis URL: {environment_variables.REDIS_URL}")
    logger.info(f"Workspace Root: {environment_variables.CLAUDE_WORKSPACE_ROOT}")
    logger.info(f"ANTHROPIC_API_KEY: {'SET' if os.environ.get('ANTHROPIC_API_KEY') else 'NOT SET (will fail when activity runs)'}")

    # Get all standard AgentEx activities
    activities = get_all_activities()

    # Add Claude-specific activities
    activities.append(run_claude_agent_activity)
    activities.append(create_workspace_directory)

    logger.info(f"Registered {len(activities)} activities (including Claude activity)")

    # Create context interceptor (reuse from OpenAI!)
    context_interceptor = ContextInterceptor()

    # Create worker with interceptor
    worker = AgentexWorker(
        task_queue=environment_variables.WORKFLOW_TASK_QUEUE,
        interceptors=[context_interceptor],  # Threads task_id to activities!
        plugins=[],  # No plugin for MVP - manual activity wrapping
    )

    logger.info("=" * 80)
    logger.info("🚀 WORKER READY - Listening for tasks...")
    logger.info("=" * 80)

    # Run worker
    await worker.run(
        activities=activities,
        workflow=ClaudeMvpWorkflow,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Worker stopped by user")
    except Exception as e:
        logger.error(f"❌ Worker failed: {e}", exc_info=True)
        raise
