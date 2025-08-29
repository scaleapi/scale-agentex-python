"""
Simplified OpenAI Agent Chat Tutorial - Agent Platform Integration

This demonstrates the new agent platform integration that reduces complexity
from 277 lines to ~30 lines while maintaining full ACP compatibility and 
Agentex infrastructure benefits.

Key benefits:
- Automatic Temporal activity orchestration
- Built-in error handling and retries
- Direct OpenAI Agents SDK integration
- Preserved ACP protocol compatibility
- Platform-agnostic design for future extensibility
"""

import os
from dotenv import load_dotenv
from temporalio import workflow

from agentex.lib.core.temporal.agent_platforms.workflow import OpenAIAgentWorkflow
from agentex.lib.environment_variables import EnvironmentVariables
from agents import Agent

environment_variables = EnvironmentVariables.refresh()
load_dotenv(dotenv_path=".env")

if not environment_variables.WORKFLOW_NAME:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At040OpenAITemporalIntegration(OpenAIAgentWorkflow):
    """
    Simplified OpenAI agent using platform integration.
    
    This replaces the complex manual orchestration with a simple
    agent configuration approach.
    """
    
    async def create_agent(self) -> Agent:
        """
        Define the OpenAI agent configuration.
        
        This is the only method you need to implement - the base class
        handles all the ACP integration, state management, and temporal
        orchestration automatically.
        """
        return Agent(
            name="Tool-Enabled Assistant",
            model="gpt-4o-mini", 
            instructions=(
                "You are a helpful assistant that can answer questions "
                "using various tools. Use tools when appropriate to provide "
                "accurate and helpful responses."
            ),
            tools=[],  # Add tools here as needed
        )

# That's it! Compare this to the 277-line manual orchestration version.
# The agent platform integration handles:
# - ACP event processing
# - Message creation and sending  
# - State management across workflow restarts
# - Error handling and recovery
# - Temporal activity durability
# - Tool execution with automatic retries
