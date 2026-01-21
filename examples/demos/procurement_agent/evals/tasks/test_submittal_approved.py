"""
Tests for Submittal_Approved event handling.

Verifies:
- Purchase order is issued (tool call)
- Procurement item created in DB with correct status and PO ID
"""
import pytest

from evals.conftest import (
    send_event,
    get_workflow_id,
    wait_for_processing,
    get_workflow_transcript,
)
from evals.fixtures.events import create_submittal_approved
from evals.graders.database import assert_procurement_item_exists
from evals.graders.tool_calls import assert_required_tools


@pytest.mark.asyncio
async def test_submittal_01_steel_beams(workflow_handle):
    """
    Test Submittal_Approved for Steel Beams.

    Expected:
    - issue_purchase_order tool called
    - create_procurement_item_activity called
    - DB has procurement item with status and PO ID
    """
    item = "Steel Beams"
    workflow_id = get_workflow_id(workflow_handle)

    # Send event
    event = create_submittal_approved(item)
    await send_event(workflow_handle, event)

    # Wait for processing
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Get transcript and verify tool calls
    transcript = await get_workflow_transcript(workflow_handle)
    assert_required_tools(transcript, [
        "issue_purchase_order",
        "create_procurement_item_activity",  # Activity name in Temporal
    ])

    # Verify DB state
    await assert_procurement_item_exists(
        workflow_id=workflow_id,
        item=item,
        expected_status="purchase_order_issued",
        expected_po_id_not_null=True,
    )


@pytest.mark.asyncio
async def test_submittal_02_hvac_units(workflow_handle):
    """
    Test Submittal_Approved for HVAC Units.

    Same expectations as Steel Beams - verifies consistency.
    """
    item = "HVAC Units"
    workflow_id = get_workflow_id(workflow_handle)

    # Send event
    event = create_submittal_approved(item)
    await send_event(workflow_handle, event)

    # Wait for processing
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Get transcript and verify tool calls
    transcript = await get_workflow_transcript(workflow_handle)
    assert_required_tools(transcript, [
        "issue_purchase_order",
        "create_procurement_item_activity",
    ])

    # Verify DB state
    await assert_procurement_item_exists(
        workflow_id=workflow_id,
        item=item,
        expected_status="purchase_order_issued",
        expected_po_id_not_null=True,
    )
