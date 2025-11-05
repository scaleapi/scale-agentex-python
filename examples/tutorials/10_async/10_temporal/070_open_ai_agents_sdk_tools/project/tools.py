from datetime import timedelta

from agents import function_tool
from temporalio import workflow

from project.activities import deposit_money, withdraw_money

# ============================================================================
# PATTERN 2 EXAMPLE: Multiple Activities Within Tools
# ============================================================================
# This demonstrates how to create a single tool that orchestrates multiple
# Temporal activities internally. This pattern is ideal when you need to:
# 1. Guarantee the sequence of operations (withdraw THEN deposit)
# 2. Make the entire operation atomic from the agent's perspective
# 3. Avoid relying on the LLM to correctly sequence multiple tool calls

@function_tool
async def move_money(from_account: str, to_account: str, amount: float) -> str:
    """Move money from one account to another atomically.
    
    This tool demonstrates PATTERN 2: Instead of having the LLM make two separate
    tool calls (withdraw + deposit), we create ONE tool that internally coordinates
    multiple activities. This guarantees:
    - withdraw_money activity runs first
    - deposit_money activity only runs if withdrawal succeeds
    - Both operations are durable and will retry on failure
    - The entire operation appears atomic to the agent
    """
    
    # STEP 1: Start the withdrawal activity
    # This creates a Temporal activity that will be retried if it fails
    withdraw_handle = workflow.start_activity_method(
        withdraw_money,
        start_to_close_timeout=timedelta(days=1)  # Long timeout for banking operations
    )

    # Wait for withdrawal to complete before proceeding
    # If this fails, the entire tool call fails and can be retried
    await withdraw_handle.result()

    # STEP 2: Only after successful withdrawal, start the deposit activity
    # This guarantees the sequence: withdraw THEN deposit
    deposit_handle = workflow.start_activity_method(
        deposit_money,
        start_to_close_timeout=timedelta(days=1)
    )

    # Wait for deposit to complete
    await deposit_handle.result()

    # PATTERN 2 BENEFIT: From the agent's perspective, this was ONE tool call
    # But in Temporal UI, you'll see TWO activities executed in sequence
    # Each activity gets its own retry logic and durability guarantees
    return f"Successfully moved ${amount} from {from_account} to {to_account}"
