import random
import asyncio

from temporalio import activity

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
# ============================================================================
# Temporal Activities for OpenAI Agents SDK Integration
# ============================================================================
# This file defines Temporal activities that can be used in two different patterns:
# 
# PATTERN 1: Direct conversion to agent tools using activity_as_tool()
# PATTERN 2: Called internally by function_tools for multi-step operations
#
# Activities represent NON-DETERMINISTIC operations that need durability:
# - API calls, database queries, file I/O, network operations
# - Any operation that could fail and needs automatic retries
# - Operations with variable latency or external dependencies

# ============================================================================
# PATTERN 1 EXAMPLE: Simple External Tool as Activity
# ============================================================================
# This activity demonstrates PATTERN 1 usage:
# - Single non-deterministic operation (simulated API call)
# - Converted directly to an agent tool using activity_as_tool()
# - Each tool call creates exactly ONE activity in the workflow

@activity.defn
async def get_weather(city: str) -> str:
    """Get the weather for a given city.
    
    PATTERN 1 USAGE: This activity gets converted to an agent tool using:
    activity_as_tool(get_weather, start_to_close_timeout=timedelta(seconds=10))
    
    When the agent calls the weather tool:
    1. This activity runs with Temporal durability guarantees
    2. If it fails, Temporal automatically retries it
    3. The result is returned directly to the agent
    """
    # Simulate API call to weather service
    if city == "New York City":
        return "The weather in New York City is 22 degrees Celsius"
    else:
        return "The weather is unknown"

# ============================================================================
# PATTERN 2 EXAMPLES: Activities Used Within Function Tools
# ============================================================================
# These activities demonstrate PATTERN 2 usage:
# - Called internally by the move_money function tool (see tools.py)
# - Multiple activities coordinated by a single tool
# - Guarantees execution sequence and atomicity

@activity.defn
async def withdraw_money(from_account: str, amount: float) -> str:
    """Withdraw money from an account.
    
    PATTERN 2 USAGE: This activity is called internally by the move_money tool.
    It's NOT converted to an agent tool directly - instead, it's orchestrated
    by code inside the function_tool to guarantee proper sequencing.
    """
    # Simulate variable API call latency (realistic for banking operations)
    random_delay = random.randint(1, 5)
    await asyncio.sleep(random_delay)
    
    # In a real implementation, this would make an API call to a banking service
    logger.info(f"Withdrew ${amount} from {from_account}")
    return f"Successfully withdrew ${amount} from {from_account}"

@activity.defn
async def deposit_money(to_account: str, amount: float) -> str:
    """Deposit money into an account.
    
    PATTERN 2 USAGE: This activity is called internally by the move_money tool
    AFTER the withdraw_money activity succeeds. This guarantees the proper
    sequence: withdraw → deposit, making the operation atomic.
    """
    # Simulate banking API latency
    await asyncio.sleep(2)
    
    # In a real implementation, this would make an API call to a banking service
    logger.info(f"Successfully deposited ${amount} into {to_account}")
    return f"Successfully deposited ${amount} into {to_account}"

# ============================================================================
# KEY INSIGHTS:
# ============================================================================
# 
# 1. ACTIVITY DURABILITY: All activities are automatically retried by Temporal
#    if they fail, providing resilience against network issues, service outages, etc.
#
# 2. PATTERN 1 vs PATTERN 2 CHOICE:
#    - Use Pattern 1 for simple, independent operations
#    - Use Pattern 2 when you need guaranteed sequencing of multiple operations
#
# 3. OBSERVABILITY: Each activity execution appears in the Temporal UI with:
#    - Execution time, retry attempts, input parameters, return values
#    - Full traceability from agent tool call to activity execution
#
# 4. PARAMETERS: Notice how Pattern 2 activities now accept proper parameters
#    (from_account, to_account, amount) that get passed through from the tool
# ============================================================================
