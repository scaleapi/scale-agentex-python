"""
Tests for Shipment_Departed_Factory event handling.

CRITICAL: These tests catch the false positive issue where the agent
incorrectly flags conflicts when ETA is before the required_by date.

Conflict logic:
- Flag if ETA >= required_by (zero/negative buffer)
- Don't flag if ETA < required_by (has buffer remaining)
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
    create_shipment_departed,
    create_submittal_approved,
)
from evals.graders.database import assert_procurement_item_exists
from evals.graders.tool_calls import assert_required_tools, assert_forbidden_tools


async def setup_submittal_approved(workflow_handle, item: str) -> None:
    """Helper to set up item through submittal approved state."""
    event = create_submittal_approved(item)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)


# =============================================================================
# NO FLAG CASES - ETA < required_by
# =============================================================================

@pytest.mark.asyncio
async def test_departed_01_no_flag_5_days_early(workflow_handle):
    """
    Steel Beams: ETA 2026-02-10, Required 2026-02-15
    5 days early - well within buffer, should NOT flag.
    """
    item = "Steel Beams"
    workflow_id = get_workflow_id(workflow_handle)

    # Setup: submittal approved first
    await setup_submittal_approved(workflow_handle, item)

    # Get transcript count BEFORE sending departed event
    previous_count = await get_transcript_event_count(workflow_handle)

    # Send shipment departed with ETA 5 days early
    eta = datetime(2026, 2, 10, 14, 30)  # Feb 10
    event = create_shipment_departed(item, eta=eta)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    # Verify tool calls for THIS EVENT ONLY
    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, ["update_procurement_item_activity"])
    assert_forbidden_tools(new_tool_calls, ["flag_potential_issue"])  # MUST NOT FLAG

    # Verify DB state
    await assert_procurement_item_exists(
        workflow_id=workflow_id,
        item=item,
        expected_status="shipment_departed",
    )


@pytest.mark.asyncio
async def test_departed_02_no_flag_1_day_early(workflow_handle):
    """
    Steel Beams: ETA 2026-02-14, Required 2026-02-15
    1 day early - boundary case but still OK, should NOT flag.
    """
    item = "Steel Beams"
    workflow_id = get_workflow_id(workflow_handle)

    await setup_submittal_approved(workflow_handle, item)

    previous_count = await get_transcript_event_count(workflow_handle)

    eta = datetime(2026, 2, 14, 14, 30)  # Feb 14 - 1 day before required
    event = create_shipment_departed(item, eta=eta)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, ["update_procurement_item_activity"])
    assert_forbidden_tools(new_tool_calls, ["flag_potential_issue"])  # MUST NOT FLAG


@pytest.mark.asyncio
async def test_departed_05_no_flag_windows_10_days_early(workflow_handle):
    """
    Windows: ETA 2026-03-05, Required 2026-03-15
    10 days early - uses buffer but still OK, should NOT flag.
    """
    item = "Windows"
    workflow_id = get_workflow_id(workflow_handle)

    await setup_submittal_approved(workflow_handle, item)

    previous_count = await get_transcript_event_count(workflow_handle)

    eta = datetime(2026, 3, 5, 16, 0)  # Mar 5 - 10 days before required
    event = create_shipment_departed(item, eta=eta)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, ["update_procurement_item_activity"])
    assert_forbidden_tools(new_tool_calls, ["flag_potential_issue"])  # MUST NOT FLAG


@pytest.mark.asyncio
async def test_departed_06_no_flag_hvac_1_day_early(workflow_handle):
    """
    HVAC Units: ETA 2026-02-28, Required 2026-03-01
    1 day early - tight boundary case, should NOT flag.
    """
    item = "HVAC Units"
    workflow_id = get_workflow_id(workflow_handle)

    await setup_submittal_approved(workflow_handle, item)

    previous_count = await get_transcript_event_count(workflow_handle)

    eta = datetime(2026, 2, 28, 11, 0)  # Feb 28 - 1 day before Mar 1
    event = create_shipment_departed(item, eta=eta)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, ["update_procurement_item_activity"])
    assert_forbidden_tools(new_tool_calls, ["flag_potential_issue"])  # MUST NOT FLAG


# =============================================================================
# FLAG CASES - ETA >= required_by
# =============================================================================

@pytest.mark.asyncio
async def test_departed_03_flag_on_deadline(workflow_handle):
    """
    Steel Beams: ETA 2026-02-15, Required 2026-02-15
    Arrives ON deadline - zero buffer, SHOULD FLAG.
    """
    item = "Steel Beams"
    workflow_id = get_workflow_id(workflow_handle)

    await setup_submittal_approved(workflow_handle, item)

    previous_count = await get_transcript_event_count(workflow_handle)

    eta = datetime(2026, 2, 15, 14, 30)  # Feb 15 = required date
    event = create_shipment_departed(item, eta=eta)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, [
        "flag_potential_issue",  # MUST FLAG
        "update_procurement_item_activity",
    ])


@pytest.mark.asyncio
async def test_departed_04_flag_late(workflow_handle):
    """
    Steel Beams: ETA 2026-02-20, Required 2026-02-15
    5 days LATE - definite conflict, SHOULD FLAG.
    """
    item = "Steel Beams"
    workflow_id = get_workflow_id(workflow_handle)

    await setup_submittal_approved(workflow_handle, item)

    previous_count = await get_transcript_event_count(workflow_handle)

    eta = datetime(2026, 2, 20, 14, 30)  # Feb 20 - 5 days after required
    event = create_shipment_departed(item, eta=eta)
    await send_event(workflow_handle, event)
    await wait_for_processing(workflow_handle, timeout_seconds=30)

    full_transcript = await get_workflow_transcript(workflow_handle)
    new_tool_calls = get_new_tool_calls(full_transcript, previous_count)
    assert_required_tools(new_tool_calls, [
        "flag_potential_issue",  # MUST FLAG
        "update_procurement_item_activity",
    ])
