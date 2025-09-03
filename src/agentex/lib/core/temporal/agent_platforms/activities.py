"""
Agent platform activities - Temporal activities for platform-specific agent execution.

These activities provide the proper async execution context for different agent
frameworks that may not work directly within Temporal workflow constraints.
"""

from typing import Any, Dict

from temporalio import activity
from agents import Agent, Runner, ModelSettings

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

@activity.defn(name="openai_agent_execution")
async def openai_agent_execution(params: Dict[str, Any]) -> str:
    """
    Execute OpenAI agent in proper async activity context.
    
    OpenAI Agents SDK requires full async context including executor access
    which isn't available in Temporal workflow execution environment.
    
    Args:
        params: Dictionary with agent_config, user_input, task_id
        
    Returns:
        str: Agent's response output
    """
    agent_config = params["agent_config"]
    user_input = params["user_input"] 
    task_id = params["task_id"]
    
    try:
        # Handle serialized config - convert dicts back to proper types
        cleaned_config = {}
        for key, value in agent_config.items():
            if key == "model_settings" and isinstance(value, dict):
                # Convert dict back to ModelSettings instance
                cleaned_config[key] = ModelSettings(**value)
            else:
                cleaned_config[key] = value
        
        # Create agent from cleaned config
        agent = Agent(**cleaned_config)
        
        # Execute agent with user input in proper async context
        logger.debug(f"Executing OpenAI agent for task {task_id} with input: {user_input[:100]}...")
        result = await Runner.run(starting_agent=agent, input=user_input)
        
        # Extract final output
        output = result.final_output if hasattr(result, 'final_output') else str(result)
        
        logger.debug(f"OpenAI agent execution completed for task {task_id}")
        return output
        
    except Exception as e:
        logger.error(f"OpenAI agent execution failed for task {task_id}: {e}")
        raise


@activity.defn(name="langchain_agent_execution") 
async def langchain_agent_execution(params: Dict[str, Any]) -> str:
    """
    Execute LangChain agent in proper async activity context (future implementation).
    """
    # TODO: Implement when LangChain strategy is added
    raise NotImplementedError("LangChain agent execution not yet implemented")


@activity.defn(name="crewai_agent_execution")
async def crewai_agent_execution(params: Dict[str, Any]) -> str:
    """
    Execute CrewAI agent in proper async activity context (future implementation).  
    """
    # TODO: Implement when CrewAI strategy is added
    raise NotImplementedError("CrewAI agent execution not yet implemented")
