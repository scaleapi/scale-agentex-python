"""
AgentexToolAdapter - Convert Agentex activities to platform-specific tools.

This utility allows existing Agentex activities to be used as tools within
different agent platforms, maintaining durability and Temporal orchestration
while providing platform-native tool interfaces.
"""

from typing import Any, Callable, Dict
from temporalio import workflow
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

class AgentexToolAdapter:
    """Adapter to convert Agentex activities to different agent platform tool formats"""
    
    @staticmethod
    def to_openai_tool(activity_func: Callable, description: str = None, parameters_schema: Dict[str, Any] = None):
        """
        Convert Agentex activity to OpenAI Function Tool.
        
        Args:
            activity_func: The Agentex activity function to wrap
            description: Optional description for the tool
            parameters_schema: Optional JSON schema for parameters
            
        Returns:
            dict: OpenAI function tool specification
        """
        try:
            from agents import FunctionTool
            
            # Extract function metadata
            func_name = activity_func.__name__
            func_description = description or getattr(activity_func, '__doc__', f"Execute {func_name} activity")
            
            # Default parameter schema if none provided
            if parameters_schema is None:
                parameters_schema = {
                    "type": "object", 
                    "properties": {
                        "params": {
                            "type": "object",
                            "description": "Parameters for the activity"
                        }
                    },
                    "required": ["params"]
                }
            
            def tool_wrapper(context, args):
                """
                Wrapper that executes the activity through Temporal workflow.
                
                This ensures the activity call is durable and benefits from
                Temporal's retry policies, timeouts, and error handling.
                """
                try:
                    logger.debug(f"Executing Agentex activity {func_name} with args: {args}")
                    
                    # Execute activity through Temporal for durability
                    result = workflow.execute_activity(
                        activity_func,
                        args.get('params', {}),
                        schedule_to_close_timeout=workflow.info().get_workflow_timeout(),
                    )
                    
                    logger.debug(f"Activity {func_name} completed successfully")
                    return result
                    
                except Exception as e:
                    logger.error(f"Activity {func_name} failed: {e}")
                    return f"Error executing {func_name}: {str(e)}"
            
            return FunctionTool(
                name=func_name,
                description=func_description,
                parameters=parameters_schema,
                on_invoke_tool=tool_wrapper
            )
            
        except ImportError:
            logger.error("OpenAI Agents SDK not available for tool conversion")
            raise RuntimeError("OpenAI Agents SDK is required for OpenAI tool conversion")
    
    @staticmethod
    def to_langchain_tool(activity_func: Callable, description: str = None):
        """
        Convert Agentex activity to LangChain Tool (future implementation).
        
        Args:
            activity_func: The Agentex activity function to wrap
            description: Optional description for the tool
            
        Returns:
            LangChain Tool instance
        """
        # TODO: Implement when LangChain strategy is added
        raise NotImplementedError("LangChain tool conversion not yet implemented")
    
    @staticmethod
    def to_crewai_tool(activity_func: Callable, description: str = None):
        """
        Convert Agentex activity to CrewAI Tool (future implementation).
        
        Args:
            activity_func: The Agentex activity function to wrap  
            description: Optional description for the tool
            
        Returns:
            CrewAI Tool instance
        """
        # TODO: Implement when CrewAI strategy is added
        raise NotImplementedError("CrewAI tool conversion not yet implemented")
    
    @staticmethod
    def create_tool_registry(activity_functions: list[Callable], platform: str = "openai") -> list:
        """
        Create a registry of tools from multiple activity functions.
        
        Args:
            activity_functions: List of Agentex activity functions
            platform: Target platform ("openai", "langchain", "crewai")
            
        Returns:
            list: Platform-specific tool instances
        """
        tools = []
        
        for activity_func in activity_functions:
            try:
                if platform == "openai":
                    tool = AgentexToolAdapter.to_openai_tool(activity_func)
                elif platform == "langchain":
                    tool = AgentexToolAdapter.to_langchain_tool(activity_func)
                elif platform == "crewai":
                    tool = AgentexToolAdapter.to_crewai_tool(activity_func)
                else:
                    logger.warning(f"Unknown platform: {platform}, skipping {activity_func.__name__}")
                    continue
                
                tools.append(tool)
                logger.debug(f"Created {platform} tool for activity: {activity_func.__name__}")
                
            except Exception as e:
                logger.error(f"Failed to convert activity {activity_func.__name__} to {platform} tool: {e}")
        
        logger.info(f"Created {len(tools)} {platform} tools from {len(activity_functions)} activities")
        return tools


# Convenience functions for common use cases

def create_openai_tools_from_activities(activity_functions: list[Callable]) -> list:
    """
    Convenience function to create OpenAI tools from Agentex activities.
    
    Args:
        activity_functions: List of Agentex activity functions
        
    Returns:
        list: OpenAI Function Tool instances
    """
    return AgentexToolAdapter.create_tool_registry(activity_functions, platform="openai")


def create_search_tool(search_activity: Callable):
    """
    Create a search tool from an Agentex search activity.
    
    Example usage in agent workflow:
    ```python
    from agentex.lib.core.temporal.activities.custom import my_search_activity
    
    search_tool = create_search_tool(my_search_activity)
    
    agent = Agent(
        name="Search Agent",
        tools=[search_tool],
        # ...
    )
    ```
    """
    return AgentexToolAdapter.to_openai_tool(
        activity_func=search_activity,
        description="Search for information using Agentex search capabilities",
        parameters_schema={
            "type": "object",
            "properties": {
                "params": {
                    "type": "object", 
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        }
                    },
                    "required": ["query"]
                }
            },
            "required": ["params"]
        }
    )
