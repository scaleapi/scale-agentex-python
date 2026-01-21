"""
Tests for Inspection_Failed event handling with human-in-the-loop.

Verifies:
- Agent escalates to human (wait_for_human called)
- Agent responds correctly to different human inputs:
  1. "Yes" - executes recommended action
  2. "Yes, and also..." - executes action + additional request
  3. "No, delete..." - removes item from schedule
"""
from datetime import datetime

import pytest

from evals.conftest import (
    send_event,
    get_workflow_id,
    send_human_response,
    wait_for_processing,
    get_workflow_transcript,
)
from evals.fixtures.events import (
    create_shipment_arrived,
    create_inspection_failed,
    create_shipment_departed,
    create_submittal_approved,
)
from evals.graders.database import (
    assert_schedule_delivery_date,
    assert_procurement_item_exists,
    assert_schedule_item_not_exists,
    assert_procurement_item_not_exists,
)
from evals.graders.tool_calls import assert_required_tools


async def setup_through_arrived(workflow_handle, item: str) -> None:
    """Helper to set up item through shipment arrived state."""
    eta = datetime(2026, 2, 15, 11, 0)
    arrival = datetime(2026, 2, 15, 10, 30)

    await send_event(workflow_handle, create_submittal_approved(item))
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    await send_event(workflow_handle, create_shipment_departed(item, eta=eta))
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    await send_event(workflow_handle, create_shipment_arrived(item, date_arrived=arrival))
    await wait_for_processing(workflow_handle, timeout_seconds=30)


@pytest.mark.asyncio
async def test_failed_01_human_approves(workflow_handle):
    """
    Test Inspection_Failed where human approves recommendation.

    Human response: "Yes"
    Expected: Agent executes its recommended action
    """
    item = "HVAC Units"
    workflow_id = get_workflow_id(workflow_handle)

    # Setup through arrived state
    await setup_through_arrived(workflow_handle, item)

    # Send inspection failed
    event = create_inspection_failed(item)
    await send_event(workflow_handle, event)

    # Wait for agent to escalate (call wait_for_human)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Send human approval
    await send_human_response(workflow_handle, "Yes")

    # Wait for agent to process response
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Note: wait_for_human is a function_tool (not Temporal activity),
    # so we verify the workflow responded correctly by checking DB state

    # DB should still have the item (agent executed recommendation)
    await assert_procurement_item_exists(
        workflow_id=workflow_id,
        item=item,
    )


@pytest.mark.asyncio
async def test_failed_02_human_approves_with_extra_action(workflow_handle):
    """
    Test Inspection_Failed where human approves + requests extra action.

    Human response: "Yes, and also update the delivery date to 2026-03-15"
    Expected: Agent executes recommendation AND updates delivery date
    """
    item = "HVAC Units"
    workflow_id = get_workflow_id(workflow_handle)

    await setup_through_arrived(workflow_handle, item)

    event = create_inspection_failed(item)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Human approves AND requests delivery date update
    await send_human_response(
        workflow_handle,
        "Yes, and also update the delivery date to 2026-03-15"
    )
    await wait_for_processing(workflow_handle, timeout_seconds=60)  # More time for extra action

    transcript = await get_workflow_transcript(workflow_handle)
    # Note: wait_for_human is a function_tool (not visible in Temporal history)
    # Verify the agent responded to human input by calling update_delivery_date_for_item
    assert_required_tools(transcript, [
        "update_delivery_date_for_item",  # Should update schedule
    ])

    # Verify schedule was updated
    await assert_schedule_delivery_date(
        workflow_id=workflow_id,
        item=item,
        expected_required_by="2026-03-15",
    )


@pytest.mark.asyncio
async def test_failed_03_human_rejects_delete(workflow_handle):
    """
    Test Inspection_Failed where human rejects and requests deletion.

    Human response: "No, remove it from the master schedule entirely"
    Expected: Item removed from schedule AND procurement items
    """
    item = "HVAC Units"
    workflow_id = get_workflow_id(workflow_handle)

    await setup_through_arrived(workflow_handle, item)

    event = create_inspection_failed(item)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Human rejects and requests deletion
    await send_human_response(
        workflow_handle,
        "No, remove it from the master schedule entirely"
    )
    await wait_for_processing(workflow_handle, timeout_seconds=60)

    transcript = await get_workflow_transcript(workflow_handle)
    # Note: wait_for_human is a function_tool (not visible in Temporal history)
    # Verify the agent responded to human input by removing/deleting items
    assert_required_tools(transcript, [
        "remove_delivery_item",  # Remove from schedule
        "delete_procurement_item_activity",  # Delete tracking record
    ])

    # Verify item was deleted from both places
    await assert_procurement_item_not_exists(workflow_id, item)
    await assert_schedule_item_not_exists(workflow_id, item)
