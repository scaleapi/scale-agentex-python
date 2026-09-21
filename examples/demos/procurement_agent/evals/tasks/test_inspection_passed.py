"""
Tests for Inspection_Passed event handling.

Verifies:
- Procurement item status updated to passed
- No escalation to human (forbidden tools)
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
    create_inspection_passed,
    create_shipment_departed,
    create_submittal_approved,
)
from evals.graders.database import assert_procurement_item_exists
from evals.graders.tool_calls import assert_required_tools, assert_forbidden_tools


async def setup_through_arrived(workflow_handle, item: str, eta: datetime, arrival: datetime) -> None:
    """Helper to set up item through shipment arrived state."""
    await send_event(workflow_handle, create_submittal_approved(item))
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    await send_event(workflow_handle, create_shipment_departed(item, eta=eta))
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    await send_event(workflow_handle, create_shipment_arrived(item, date_arrived=arrival))
    await wait_for_processing(workflow_handle, timeout_seconds=30)


@pytest.mark.asyncio
async def test_passed_01_steel_beams(workflow_handle):
    """
    Test Inspection_Passed for Steel Beams.

    Expected:
    - update_procurement_item_activity called
    - NO wait_for_human (should not escalate on success)
    - NO flag_potential_issue
    - DB shows inspection_passed status
    """
    item = "Steel Beams"
    workflow_id = get_workflow_id(workflow_handle)

    eta = datetime(2026, 2, 10, 14, 30)
    arrival = datetime(2026, 2, 10, 15, 45)
    await setup_through_arrived(workflow_handle, item, eta, arrival)

    # Get transcript count BEFORE sending inspection_passed
    previous_count = await get_transcript_event_count(workflow_handle)

    # Send inspection passed
    event = create_inspection_passed(item)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Verify tool calls for THIS EVENT ONLY (not entire workflow)
    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, ["update_procurement_item_activity"])
    assert_forbidden_tools(new_tool_calls, [
        "wait_for_human",  # Should NOT escalate on success
        "flag_potential_issue",  # Should NOT flag issues
    ])

    # Verify DB state
    await assert_procurement_item_exists(
        workflow_id=workflow_id,
        item=item,
        expected_status="inspection_passed",
    )


@pytest.mark.asyncio
async def test_passed_02_windows(workflow_handle):
    """
    Test Inspection_Passed for Windows.

    Same expectations as Steel Beams.
    """
    item = "Windows"
    workflow_id = get_workflow_id(workflow_handle)

    eta = datetime(2026, 3, 5, 16, 0)
    arrival = datetime(2026, 3, 5, 16, 20)
    await setup_through_arrived(workflow_handle, item, eta, arrival)

    # Get transcript count BEFORE sending inspection_passed
    previous_count = await get_transcript_event_count(workflow_handle)

    event = create_inspection_passed(item)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Verify tool calls for THIS EVENT ONLY
    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, ["update_procurement_item_activity"])
    assert_forbidden_tools(new_tool_calls, ["wait_for_human", "flag_potential_issue"])

    await assert_procurement_item_exists(
        workflow_id=workflow_id,
        item=item,
        expected_status="inspection_passed",
    )
