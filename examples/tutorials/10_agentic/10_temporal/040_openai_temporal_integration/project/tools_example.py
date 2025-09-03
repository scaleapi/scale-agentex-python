"""
Example demonstrating AgentexToolAdapter usage.

This shows how to convert existing Agentex activities into OpenAI agent tools,
maintaining full Temporal durability and orchestration benefits.
"""

from agents import Agent
from agentex.lib.core.temporal.agent_platforms import (
    AgentexToolAdapter, 
    create_openai_tools_from_activities,
    create_search_tool
)

# Example: Convert a hypothetical search activity to OpenAI tool
def example_search_activity(params):
    """Example search activity that could be converted to a tool"""
    query = params.get('query', '')
    # In real implementation, this would be a proper Agentex activity
    return f"Search results for: {query}"

def example_calculation_activity(params):
    """Example calculation activity"""
    expression = params.get('expression', '')
    # In real implementation, this would be a proper Agentex activity with @activity.defn
    try:
        result = eval(expression)  # Note: eval is dangerous, just for demo
        return f"Result: {result}"
    except:
        return "Invalid expression"

# Example usage in an agent workflow
def create_agent_with_tools():
    """
    Example of creating an OpenAI agent with Agentex activities as tools.
    
    This shows how the AgentexToolAdapter bridges the gap between 
    Agentex activities and OpenAI agent tools.
    """
    
    # Method 1: Individual tool conversion
    search_tool = AgentexToolAdapter.to_openai_tool(
        activity_func=example_search_activity,
        description="Search for information across various sources",
        parameters_schema={
            "type": "object",
            "properties": {
                "params": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string", 
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]
                }
            },
            "required": ["params"]
        }
    )
    
    # Method 2: Bulk conversion of multiple activities
    activity_functions = [example_search_activity, example_calculation_activity]
    tools = create_openai_tools_from_activities(activity_functions)
    
    # Method 3: Convenience function for common patterns
    search_tool_2 = create_search_tool(example_search_activity)
    
    # Create agent with converted tools
    agent = Agent(
        name="Tool-Enabled Assistant",
        model="gpt-4o-mini",
        instructions=(
            "You are a helpful assistant with access to search and calculation tools. "
            "Use the tools when appropriate to provide accurate information."
        ),
        tools=[search_tool, *tools, search_tool_2],
    )
    
    return agent

# Example showing the benefit: Temporal durability
"""
When the agent uses these tools:
1. Tool call gets converted to Temporal activity execution
2. Benefits from automatic retries, timeouts, error handling
3. Maintains durability across workflow restarts
4. Preserves all Agentex observability and tracing
5. Can be monitored through Agentex infrastructure

Traditional approach:
    agent_tool() -> direct function call -> no durability

Agentex approach:  
    agent_tool() -> workflow.execute_activity() -> Temporal orchestration -> full durability
"""
