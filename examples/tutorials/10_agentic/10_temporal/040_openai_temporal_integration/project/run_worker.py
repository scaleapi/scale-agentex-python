"""
Simplified worker setup using agent platform configuration.

This demonstrates the new platform-aware worker setup that automatically
optimizes activity registration and applies platform-specific configuration.
"""

import asyncio
import os
from dotenv import load_dotenv

from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.environment_variables import EnvironmentVariables
from project.workflow import At040OpenAITemporalIntegration

load_dotenv()
environment_variables = EnvironmentVariables.refresh()

async def main():
    """
    Create and run the worker with OpenAI platform configuration.
    
    The agent_platform parameter:
    - Automatically excludes OpenAI provider activities (optimization)
    - Applies OpenAI-specific worker configuration
    - Enables platform-specific features like OpenAI plugin integration
    """
    worker = AgentexWorker(
        task_queue=environment_variables.WORKFLOW_TASK_QUEUE,
        agent_platform="openai",  # This is the key difference!
        platform_config={
            "enable_openai_plugin": True,  # Use Temporal OpenAI plugin if available
            "model_timeout": 60,           # Platform-specific timeout
        }
    )
    
    # No need to specify activities - they're automatically optimized
    # No need for complex setup - platform handles the details
    await worker.run(
        activities=[],  # Platform-optimized activities used automatically
        workflow=At040OpenAITemporalIntegration,
    )

if __name__ == "__main__":
    asyncio.run(main())
