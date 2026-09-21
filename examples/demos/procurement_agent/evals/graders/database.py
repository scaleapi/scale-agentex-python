"""
Database grader - verifies database state after agent actions.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from pathlib import Path

import aiosqlite  # type: ignore[import-not-found]

# Use the same DB path as the main application
DB_PATH = Path(__file__).parent.parent.parent / "project" / "data" / "procurement.db"


async def get_procurement_item(workflow_id: str, item: str) -> Optional[dict[str, Any]]:
    """
    Get a procurement item from the database.

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name

    Returns:
        Dict with item fields or None if not found
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT workflow_id, item, status, eta, date_arrived, purchase_order_id,
                   created_at, updated_at
            FROM procurement_items
            WHERE workflow_id = ? AND item = ?
            """,
            (workflow_id, item)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def get_schedule_delivery(workflow_id: str, item: str) -> Optional[dict[str, Any]]:
    """
    Get a delivery item from the master construction schedule.

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name

    Returns:
        Dict with delivery fields or None if not found
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT schedule_json
            FROM master_construction_schedule
            WHERE workflow_id = ?
            """,
            (workflow_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                schedule = json.loads(row["schedule_json"])
                for delivery in schedule.get("deliveries", []):
                    if delivery.get("item") == item:
                        return delivery
            return None


async def assert_procurement_item_exists(
    workflow_id: str,
    item: str,
    expected_status: Optional[str] = None,
    expected_po_id_not_null: bool = False,
    expected_eta: Optional[str] = None,
    expected_date_arrived: Optional[str] = None,
) -> dict[str, Any]:
    """
    Assert a procurement item exists with expected fields.

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name
        expected_status: If provided, assert status matches
        expected_po_id_not_null: If True, assert purchase_order_id is not null
        expected_eta: If provided, assert ETA matches
        expected_date_arrived: If provided, assert date_arrived matches

    Returns:
        The procurement item record

    Raises:
        AssertionError: If item doesn't exist or fields don't match
    """
    record = await get_procurement_item(workflow_id, item)

    if record is None:
        raise AssertionError(
            f"Procurement item not found: workflow_id={workflow_id}, item={item}"
        )

    if expected_status is not None:
        assert record["status"] == expected_status, (
            f"Expected status '{expected_status}', got '{record['status']}'"
        )

    if expected_po_id_not_null:
        assert record["purchase_order_id"] is not None, (
            "Expected purchase_order_id to be set, but it was null"
        )

    if expected_eta is not None:
        assert record["eta"] == expected_eta, (
            f"Expected ETA '{expected_eta}', got '{record['eta']}'"
        )

    if expected_date_arrived is not None:
        assert record["date_arrived"] == expected_date_arrived, (
            f"Expected date_arrived '{expected_date_arrived}', got '{record['date_arrived']}'"
        )

    return record


async def assert_procurement_item_not_exists(workflow_id: str, item: str) -> None:
    """
    Assert a procurement item does NOT exist (was deleted).

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name

    Raises:
        AssertionError: If item still exists
    """
    record = await get_procurement_item(workflow_id, item)
    if record is not None:
        raise AssertionError(
            f"Procurement item should not exist but was found: {record}"
        )


async def assert_schedule_item_not_exists(workflow_id: str, item: str) -> None:
    """
    Assert an item is NOT in the master construction schedule (was removed).

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name

    Raises:
        AssertionError: If item still in schedule
    """
    delivery = await get_schedule_delivery(workflow_id, item)
    if delivery is not None:
        raise AssertionError(
            f"Schedule item should not exist but was found: {delivery}"
        )


async def assert_schedule_delivery_date(
    workflow_id: str,
    item: str,
    expected_required_by: str
) -> None:
    """
    Assert a delivery item has the expected required_by date.

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name
        expected_required_by: The expected date string

    Raises:
        AssertionError: If date doesn't match
    """
    delivery = await get_schedule_delivery(workflow_id, item)
    if delivery is None:
        raise AssertionError(f"Schedule delivery not found for item: {item}")

    assert delivery["required_by"] == expected_required_by, (
        f"Expected required_by '{expected_required_by}', got '{delivery['required_by']}'"
    )
