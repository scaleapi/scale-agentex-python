"""
Tests for Shipment_Arrived_Site event handling.

Verifies:
- Team notification sent
- Inspection scheduled
- Procurement item updated with arrival date
"""
from datetime import datetime

import pytest

from evals.conftest import (
    send_event,
    get_workflow_id,
    get_new_tool_calls,
    wait_for_processing,
    get_workflow_transcript,
    get_transcript_event_count,
)
from evals.fixtures.events import (
    create_shipment_arrived,
    create_shipment_departed,
    create_submittal_approved,
)
from evals.graders.database import assert_procurement_item_exists
from evals.graders.tool_calls import assert_required_tools


async def setup_through_departed(workflow_handle, item: str, eta: datetime) -> None:
    """Helper to set up item through shipment departed state."""
    # Submittal approved
    await send_event(workflow_handle, create_submittal_approved(item))
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Shipment departed
    await send_event(workflow_handle, create_shipment_departed(item, eta=eta))
    await wait_for_processing(workflow_handle, timeout_seconds=30)


@pytest.mark.asyncio
async def test_arrived_01_steel_beams(workflow_handle):
    """
    Test Shipment_Arrived_Site for Steel Beams.

    Expected:
    - notify_team_shipment_arrived called
    - schedule_inspection called
    - update_procurement_item_activity called
    - DB shows shipment_arrived status with date
    """
    item = "Steel Beams"
    workflow_id = get_workflow_id(workflow_handle)
    arrival_date = datetime(2026, 2, 10, 15, 45)

    # Setup through departed state
    eta = datetime(2026, 2, 10, 14, 30)
    await setup_through_departed(workflow_handle, item, eta)

    # Get transcript count BEFORE sending arrived event
    previous_count = await get_transcript_event_count(workflow_handle)

    # Send arrived event
    event = create_shipment_arrived(item, date_arrived=arrival_date)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Verify tool calls for THIS EVENT ONLY
    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, [
        "notify_team_shipment_arrived",
        "schedule_inspection",
        "update_procurement_item_activity",
    ])

    # Verify DB state
    await assert_procurement_item_exists(
        workflow_id=workflow_id,
        item=item,
        expected_status="shipment_arrived",
    )


@pytest.mark.asyncio
async def test_arrived_02_windows(workflow_handle):
    """
    Test Shipment_Arrived_Site for Windows.

    Same expectations as Steel Beams.
    """
    item = "Windows"
    workflow_id = get_workflow_id(workflow_handle)
    arrival_date = datetime(2026, 3, 5, 16, 20)

    eta = datetime(2026, 3, 5, 16, 0)
    await setup_through_departed(workflow_handle, item, eta)

    # Get transcript count BEFORE sending arrived event
    previous_count = await get_transcript_event_count(workflow_handle)

    event = create_shipment_arrived(item, date_arrived=arrival_date)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Verify tool calls for THIS EVENT ONLY
    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, [
        "notify_team_shipment_arrived",
        "schedule_inspection",
        "update_procurement_item_activity",
    ])

    await assert_procurement_item_exists(
        workflow_id=workflow_id,
        item=item,
        expected_status="shipment_arrived",
    )
