"""Event agent for processing procurement events and taking actions."""
from __future__ import annotations

from datetime import datetime, timedelta

from agents import Agent, function_tool
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.contrib import openai_agents
from temporalio.exceptions import TimeoutError, ApplicationError

from project.activities.activities import (
    schedule_inspection,
    flag_potential_issue,
    issue_purchase_order,
    remove_delivery_item,
    update_project_end_date,
    notify_team_shipment_arrived,
    update_delivery_date_for_item,
    create_procurement_item_activity,
    delete_procurement_item_activity,
    update_procurement_item_activity,
    get_all_procurement_items_activity,
    get_procurement_item_by_name_activity,
)


@function_tool
async def wait_for_human(recommended_action: str) -> str:
    """
    When the we are stuck and need to ask a human for help, call this tool. Please provide a recommended action to the human.
    Until the human approves the recommended action, you will keep calling this tool (call it as many times as needed).
    If the human says anything other than yes, please use this tool again and come up with a new recommended action.
    If the human wants to add additional information, please use this tool again and come up with a new recommended action.
    You are almost always calling this tool again unless the human approves the exact recommended action.

    For example:

    Assistant recommendation: The inspection failed I recommend we re-order the item.
    Human response: No, we should not re-order the item. Please remove the item from the master schedule.
    Assistant recommendation: Ok I will go ahead and remove the item from the master schedule. Do you approve?
    Human response: Yes

    Assistant recommendation: The inspection failed I recommend we re-order the item.
    Human response: Yes and also please update the master schedule to reflect the new delivery date.
    Assistant recommendation: Ok I will go ahead and update the master schedule to reflect the new delivery date and re-order the item. Does that sound right?
    Human response: Yes
    """
    workflow_instance = workflow.instance()
    workflow.logger.info(f"Recommended action: {recommended_action}")

    try:
        # Wait for human response with 24-hour timeout (don't wait forever!)
        await workflow.wait_condition(
            lambda: not workflow_instance.human_queue.empty(),
            timeout=timedelta(hours=24),
        )

        while not workflow_instance.human_queue.empty():
            human_input = await workflow_instance.human_queue.get()
            print(f"[WORKFLOW] Processing human message from queue")
            return human_input

        # If queue became empty after wait_condition succeeded, this shouldn't normally happen
        workflow.logger.warning("Queue empty after wait condition succeeded")
        return "No human response available"

    except TimeoutError:
        # Human didn't respond within 24 hours
        workflow.logger.warning("Human escalation timed out after 24 hours")
        return "TIMEOUT: No human response received within 24 hours. Proceeding with best judgment."


@function_tool
async def update_delivery_date_tool(item: str, new_delivery_date: str) -> str:
    """
    Updates the delivery date for a specific item in the construction schedule.

    Call this when:
    - You want to update the delivery date for a specific item in the construction schedule
    - Human feedback requests updating the delivery date for a specific item

    Args:
        item: The item to update
        new_delivery_date: The new delivery date

    Returns:
        Confirmation message or error description
    """
    workflow_id = workflow.info().workflow_id

    retry_policy = RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
        non_retryable_error_types=["DataCorruptionError"],
    )

    try:
        return await workflow.execute_activity(
            update_delivery_date_for_item,
            args=[workflow_id, item, new_delivery_date],
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
    except ApplicationError as e:
        # Non-retryable error (item not found, schedule missing)
        workflow.logger.error(f"Failed to update delivery date for {item}: {e}")
        return f"Error: Unable to update delivery date for {item}. {e.message}"
    except Exception as e:
        # Unexpected error
        workflow.logger.error(f"Unexpected error updating delivery date: {e}")
        return f"Error: System issue updating delivery date for {item}. Please try again."


@function_tool
async def remove_delivery_item_tool(item: str) -> str:
    """
    Removes a delivery item from the construction schedule.

    Call this when:
    - You want to remove a delivery item from the construction schedule
    - Human feedback requests removing a delivery item

    Args:
        item: The item to remove

    Returns:
        Confirmation message or error description
    """
    workflow_id = workflow.info().workflow_id

    retry_policy = RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
        non_retryable_error_types=["DataCorruptionError"],
    )

    try:
        return await workflow.execute_activity(
            remove_delivery_item,
            args=[workflow_id, item],
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
    except ApplicationError as e:
        # Non-retryable error (item not found, schedule missing)
        workflow.logger.error(f"Failed to remove delivery item {item}: {e}")
        return f"Error: Unable to remove item {item}. {e.message}"
    except Exception as e:
        # Unexpected error
        workflow.logger.error(f"Unexpected error removing delivery item: {e}")
        return f"Error: System issue removing item {item}. Please try again."


@function_tool
async def update_project_end_date_tool(new_end_date: str) -> str:
    """
    Updates the end date for the project in the construction schedule.

    Call this when:
    - You want to update the end date for the project in the construction schedule
    - Human feedback requests updating the end date for the project

    Args:
        new_end_date: The new end date for the project

    Returns:
        Confirmation message or error description
    """
    workflow_id = workflow.info().workflow_id

    retry_policy = RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
        non_retryable_error_types=["DataCorruptionError"],
    )

    try:
        return await workflow.execute_activity(
            update_project_end_date,
            args=[workflow_id, new_end_date],
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
    except ApplicationError as e:
        # Non-retryable error (schedule not found)
        workflow.logger.error(f"Failed to update project end date: {e}")
        return f"Error: Unable to update project end date. {e.message}"
    except Exception as e:
        # Unexpected error
        workflow.logger.error(f"Unexpected error updating project end date: {e}")
        return f"Error: System issue updating project end date. Please try again."


@function_tool
async def create_procurement_item_tool(
    item: str,
    status: str,
    eta: str | None = None,
    date_arrived: str | None = None,
    purchase_order_id: str | None = None
) -> str:
    """
    Creates a new procurement item for tracking through the workflow.

    Call this when:
    - A submittal is approved (after calling issue_purchase_order)
    - You need to track a new item in the procurement system

    Args:
        item: The item name (e.g., "Steel Beams")
        status: Current status (e.g., "submittal_approved", "purchase_order_issued")
        eta: Optional estimated time of arrival (ISO format)
        date_arrived: Optional date the item arrived (ISO format)
        purchase_order_id: Optional purchase order ID

    Returns:
        Confirmation message or error description
    """
    workflow_id = workflow.info().workflow_id

    retry_policy = RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
        non_retryable_error_types=["DataCorruptionError"],
    )

    try:
        return await workflow.execute_activity(
            create_procurement_item_activity,
            args=[workflow_id, item, status, eta, date_arrived, purchase_order_id],
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
    except ApplicationError as e:
        # Non-retryable error (invalid data)
        workflow.logger.error(f"Failed to create procurement item for {item}: {e}")
        return f"Error: Unable to create procurement item for {item}. {e.message}"
    except Exception as e:
        # Unexpected error
        workflow.logger.error(f"Unexpected error creating procurement item: {e}")
        return f"Error: System issue creating procurement item for {item}. Please try again."


@function_tool
async def update_procurement_item_tool(
    item: str,
    status: str | None = None,
    eta: str | None = None,
    date_arrived: str | None = None,
    purchase_order_id: str | None = None
) -> str:
    """
    Updates a procurement item's fields in the tracking system.

    Call this when:
    - An event changes the item's status (e.g., shipment departed, arrived, inspection scheduled/failed/passed)
    - A purchase order is issued for the item
    - The ETA is updated
    - The item arrives at the site
    - A potential issue is flagged

    Args:
        item: The item name (e.g., "Steel Beams", "HVAC Units") - REQUIRED to identify which item to update
        status: Optional new status (e.g., "purchase_order_issued", "shipment_departed", "shipment_arrived",
                "potential_issue_flagged", "inspection_scheduled", "inspection_failed", "inspection_passed")
        eta: Optional new estimated time of arrival (ISO format)
        date_arrived: Optional new arrival date (ISO format)
        purchase_order_id: Optional new purchase order ID

    Returns:
        Confirmation message or error description
    """
    workflow_id = workflow.info().workflow_id

    retry_policy = RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
        non_retryable_error_types=["DataCorruptionError"],
    )

    try:
        return await workflow.execute_activity(
            update_procurement_item_activity,
            args=[workflow_id, item, status, eta, date_arrived, purchase_order_id],
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
    except ApplicationError as e:
        # Non-retryable error (item not found)
        workflow.logger.error(f"Failed to update procurement item: {e}")
        return f"Error: Unable to update procurement item. {e.message}"
    except Exception as e:
        # Unexpected error
        workflow.logger.error(f"Unexpected error updating procurement item: {e}")
        return f"Error: System issue updating procurement item. Please try again."


@function_tool
async def delete_procurement_item_tool(item: str) -> str:
    """
    Deletes a procurement item from the tracking system.

    Call this when:
    - Human explicitly requests removing/deleting an item
    - An item is no longer needed in the project

    Args:
        item: The item name to delete (e.g., "Steel Beams", "HVAC Units")

    Returns:
        Confirmation message or error description
    """
    workflow_id = workflow.info().workflow_id

    retry_policy = RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
        non_retryable_error_types=["DataCorruptionError"],
    )

    try:
        return await workflow.execute_activity(
            delete_procurement_item_activity,
            args=[workflow_id, item],
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
    except ApplicationError as e:
        # Non-retryable error (item not found)
        workflow.logger.error(f"Failed to delete procurement item: {e}")
        return f"Error: Unable to delete procurement item. {e.message}"
    except Exception as e:
        # Unexpected error
        workflow.logger.error(f"Unexpected error deleting procurement item: {e}")
        return f"Error: System issue deleting procurement item. Please try again."


@function_tool
async def get_procurement_item_by_name_tool(item: str) -> str:
    """
    Retrieves a procurement item by item name for context.

    Call this when:
    - You need to check the status of a specific item before making decisions
    - Human asks about the status of an item
    - You need additional context about an item

    Args:
        item: The item name (e.g., "Steel Beams")

    Returns:
        JSON string of the procurement item or message if not found
    """
    workflow_id = workflow.info().workflow_id

    retry_policy = RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
        non_retryable_error_types=["DataCorruptionError"],
    )

    try:
        return await workflow.execute_activity(
            get_procurement_item_by_name_activity,
            args=[workflow_id, item],
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
    except ApplicationError as e:
        # Non-retryable error (invalid input)
        workflow.logger.error(f"Failed to get procurement item {item}: {e}")
        return f"Error: Unable to get procurement item {item}. {e.message}"
    except Exception as e:
        # Unexpected error
        workflow.logger.error(f"Unexpected error getting procurement item: {e}")
        return f"Error: System issue getting procurement item {item}. Please try again."


@function_tool
async def get_all_procurement_items_tool() -> str:
    """
    Retrieves all procurement items for context.

    Call this when:
    - You need an overview of all procurement items
    - Human asks for a summary of all items
    - You need to check multiple items' statuses

    Returns:
        JSON string of all procurement items
    """
    retry_policy = RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
        non_retryable_error_types=["DataCorruptionError"],
    )

    try:
        return await workflow.execute_activity(
            get_all_procurement_items_activity,
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
    except ApplicationError as e:
        # Non-retryable error
        workflow.logger.error(f"Failed to get all procurement items: {e}")
        return f"Error: Unable to get all procurement items. {e.message}"
    except Exception as e:
        # Unexpected error
        workflow.logger.error(f"Unexpected error getting all procurement items: {e}")
        return f"Error: System issue getting all procurement items. Please try again."

def new_procurement_agent(master_construction_schedule: str, human_input_learnings: list) -> Agent:
    """
    Create an agent that processes procurement events and takes actions.

    Args:
        event_log: History of events that have occurred
        master_construction_schedule: Current construction schedule
        human_input_learnings: Past escalations and human decisions

    Returns:
        Agent configured to process events and call tools
    """
    instructions = f"""
You are a procurement agent for a commercial building construction project.

Your role is to monitor procurement events, take appropriate actions, and escalate critical issues to a human with a recommended action.

Please escalate to a human if you feel like we are facing a critical schedule delay and provide a recommended action.

If the user says no or has feedback, please come up with another solution and call the wait_for_human tool again (you can call it as many times as needed).

## CRITICAL: When to Flag Potential Issues (Shipment_Departed_Factory events)

When processing a Shipment_Departed_Factory event, you MUST compare the ETA to the required_by date from the master schedule:

- **ONLY flag_potential_issue if ETA >= required_by** (zero buffer or late - this is a problem!)
- **DO NOT flag_potential_issue if ETA < required_by** (there is still buffer remaining - no issue!)

Example 1: Item required_by 2026-02-15, ETA is 2026-02-10 → DO NOT FLAG (5 days buffer remaining)
Example 2: Item required_by 2026-02-15, ETA is 2026-02-15 → FLAG (zero buffer - on the deadline!)
Example 3: Item required_by 2026-02-15, ETA is 2026-02-20 → FLAG (5 days late!)

The buffer_days field in the schedule is informational only. What matters is: Does ETA arrive BEFORE the required_by date?

## Context

Master Construction Schedule:
{master_construction_schedule}

Past Learnings from Escalations:
{human_input_learnings}

Current Date: {datetime.now().isoformat()}


    """

    start_to_close_timeout = timedelta(days=1)

    return Agent(
        name="Procurement Event Agent",
        instructions=instructions,
        model="gpt-4o",
        tools=[
            openai_agents.workflow.activity_as_tool(
                issue_purchase_order, start_to_close_timeout=start_to_close_timeout
            ),
            openai_agents.workflow.activity_as_tool(
                flag_potential_issue, start_to_close_timeout=start_to_close_timeout
            ),
            openai_agents.workflow.activity_as_tool(
                notify_team_shipment_arrived,
                start_to_close_timeout=start_to_close_timeout,
            ),
            openai_agents.workflow.activity_as_tool(
                schedule_inspection, start_to_close_timeout=start_to_close_timeout
            ),
            update_delivery_date_tool,  # function_tool wrapper that injects workflow_id
            remove_delivery_item_tool,  # function_tool wrapper that injects workflow_id
            update_project_end_date_tool,  # function_tool wrapper that injects workflow_id
            create_procurement_item_tool,  # function_tool wrapper for creating procurement items
            update_procurement_item_tool,  # function_tool wrapper for updating procurement items
            delete_procurement_item_tool,  # function_tool wrapper for deleting procurement items
            get_procurement_item_by_name_tool,  # function_tool wrapper for getting a specific procurement item
            get_all_procurement_items_tool,  # function_tool wrapper for getting all procurement items
            wait_for_human,  # function_tool runs in workflow context
        ],
    )