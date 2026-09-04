"""
Database initialization and management for procurement agent.
Stores master construction schedules indexed by workflow ID.
"""
from __future__ import annotations

import json
from typing import Optional
from pathlib import Path

import aiosqlite  # type: ignore[import-untyped]

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


# Custom exceptions for database operations
class DatabaseError(Exception):
    """Platform-level database errors (retryable by Temporal)"""
    pass


class DataCorruptionError(Exception):
    """Application-level data errors (non-retryable)"""
    pass

# Database file location (in the data directory)
DB_PATH = Path(__file__).parent / "procurement.db"

DEFAULT_SCHEDULE = {
    "project": {
        "name": "Small Office Renovation",
        "start_date": "2026-02-01",
        "end_date": "2026-05-31"
    },
    "deliveries": [
        {
            "item": "Steel Beams",
            "required_by": "2026-02-15",
            "buffer_days": 5
        },
        {
            "item": "HVAC Units",
            "required_by": "2026-03-01",
            "buffer_days": 7
        },
        {
            "item": "Windows",
            "required_by": "2026-03-15",
            "buffer_days": 10
        },
        {
            "item": "Flooring Materials",
            "required_by": "2026-04-01",
            "buffer_days": 3
        },
        {
            "item": "Electrical Panels",
            "required_by": "2026-04-15",
            "buffer_days": 5
        }
    ]
}


async def init_database() -> None:
    """
    Initialize the SQLite database and create tables if they don't exist.
    Creates the master_construction_schedule and procurement_items tables.
    Safe to call multiple times - uses CREATE TABLE IF NOT EXISTS.

    Raises:
        DatabaseError: If database initialization fails
    """
    logger.info(f"Initializing database at {DB_PATH}")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS master_construction_schedule (
                    workflow_id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    project_start_date TEXT NOT NULL,
                    project_end_date TEXT NOT NULL,
                    schedule_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index on workflow_id for faster lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflow_id
                ON master_construction_schedule(workflow_id)
            """)

            # Create procurement_items table for tracking item status through workflow
            await db.execute("""
                CREATE TABLE IF NOT EXISTS procurement_items (
                    workflow_id TEXT NOT NULL,
                    item TEXT NOT NULL,
                    status TEXT NOT NULL,
                    eta TEXT,
                    date_arrived TEXT,
                    purchase_order_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (workflow_id, item)
                )
            """)

            # Create index on workflow_id for faster lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_procurement_workflow_id
                ON procurement_items(workflow_id)
            """)

            await db.commit()
            logger.info("Database initialized successfully")

    except aiosqlite.Error as e:
        # Fatal error - can't initialize database
        logger.error(f"Failed to initialize database: {e}")
        raise DatabaseError(f"Failed to initialize database: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        raise DatabaseError(f"Unexpected database initialization error: {e}") from e


async def create_schedule_for_workflow(
    workflow_id: str,
    schedule: Optional[dict] = None
) -> None:
    """
    Create a new construction schedule for a specific workflow.
    Uses default schedule if none provided.

    Args:
        workflow_id: The Temporal workflow ID
        schedule: Optional custom schedule dict. If None, uses DEFAULT_SCHEDULE

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If schedule data is invalid (non-retryable)
    """
    # Input validation - non-retryable errors
    if not workflow_id or not isinstance(workflow_id, str):
        raise DataCorruptionError("Invalid workflow_id: must be a non-empty string")

    if schedule is None:
        schedule = DEFAULT_SCHEDULE

    # Validate schedule structure - non-retryable errors
    try:
        if "project" not in schedule:
            raise DataCorruptionError("Schedule missing 'project' key")
        required_keys = ["name", "start_date", "end_date"]
        for key in required_keys:
            if key not in schedule["project"]:
                raise DataCorruptionError(f"Schedule project missing required key: {key}")
    except (TypeError, AttributeError) as e:
        raise DataCorruptionError(f"Invalid schedule structure: {e}") from e

    try:
        # Validate JSON serialization before inserting
        schedule_json = json.dumps(schedule)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO master_construction_schedule
                (workflow_id, project_name, project_start_date, project_end_date, schedule_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                workflow_id,
                schedule["project"]["name"],
                schedule["project"]["start_date"],
                schedule["project"]["end_date"],
                schedule_json
            ))
            await db.commit()
            logger.info(f"Created schedule for workflow {workflow_id}")

    except (TypeError, ValueError) as e:
        # Data error - can't serialize to JSON, don't retry
        logger.error(f"Failed to serialize schedule to JSON: {e}")
        raise DataCorruptionError(f"Schedule data cannot be serialized: {e}") from e

    except aiosqlite.IntegrityError as e:
        # Data constraint violation - don't retry
        logger.error(f"Data integrity error: {e}")
        raise DataCorruptionError(f"Data integrity error: {e}") from e

    except aiosqlite.Error as e:
        # Database connection/lock errors - retryable
        logger.warning(f"Database error creating schedule (retryable): {e}")
        raise DatabaseError(f"Failed to create schedule: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error creating schedule: {e}")
        raise DatabaseError(f"Unexpected error creating schedule: {e}") from e


async def get_schedule_for_workflow(workflow_id: str) -> Optional[dict]:
    """
    Retrieve the construction schedule for a specific workflow.

    Args:
        workflow_id: The Temporal workflow ID

    Returns:
        The schedule dict or None if not found

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If stored JSON is corrupted (non-retryable)
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT schedule_json FROM master_construction_schedule
                WHERE workflow_id = ?
            """, (workflow_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    # Validate JSON before returning
                    try:
                        return json.loads(row["schedule_json"])
                    except json.JSONDecodeError as e:
                        logger.error(f"Corrupted JSON in database for workflow {workflow_id}: {e}")
                        raise DataCorruptionError(
                            f"Schedule JSON corrupted for workflow {workflow_id}: {e}"
                        ) from e
                return None

    except DataCorruptionError:
        # Re-raise data corruption errors
        raise

    except aiosqlite.Error as e:
        # Database connection errors - retryable
        logger.warning(f"Database error retrieving schedule (retryable): {e}")
        raise DatabaseError(f"Failed to retrieve schedule: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error retrieving schedule: {e}")
        raise DatabaseError(f"Unexpected error retrieving schedule: {e}") from e

async def update_delivery_date_for_item_for_workflow(workflow_id: str, item: str, new_delivery_date: str) -> None:
    """
    Update the delivery date for a specific item in the construction schedule for a specific workflow.

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If schedule not found or item not found (non-retryable)
    """
    # Get the current schedule (may raise DatabaseError or DataCorruptionError)
    schedule = await get_schedule_for_workflow(workflow_id)
    if schedule is None:
        logger.error(f"No schedule found for workflow {workflow_id}")
        raise DataCorruptionError(f"No schedule found for workflow {workflow_id}")

    # Update the delivery item's required_by date
    updated = False
    for delivery in schedule.get("deliveries", []):
        if delivery.get("item") == item:
            delivery["required_by"] = new_delivery_date
            updated = True
            break

    if not updated:
        logger.error(f"Item {item} not found in schedule for workflow {workflow_id}")
        raise DataCorruptionError(f"Item {item} not found in schedule for workflow {workflow_id}")

    # Save the updated schedule back to the database
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE master_construction_schedule
                SET schedule_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE workflow_id = ?
            """, (json.dumps(schedule), workflow_id))
            await db.commit()
            logger.info(f"Updated delivery date for item {item} in workflow {workflow_id}")

    except aiosqlite.Error as e:
        # Database connection errors - retryable
        logger.warning(f"Database error updating delivery date (retryable): {e}")
        raise DatabaseError(f"Failed to update delivery date: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error updating delivery date: {e}")
        raise DatabaseError(f"Unexpected error updating delivery date: {e}") from e

async def remove_delivery_item_for_workflow(workflow_id: str, item: str) -> None:
    """
    Remove a delivery item from the construction schedule for a specific workflow.

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If schedule not found or item not found (non-retryable)
    """
    # Get the current schedule (may raise DatabaseError or DataCorruptionError)
    schedule = await get_schedule_for_workflow(workflow_id)
    if schedule is None:
        logger.error(f"No schedule found for workflow {workflow_id}")
        raise DataCorruptionError(f"No schedule found for workflow {workflow_id}")

    # Remove the delivery item from the list
    original_count = len(schedule.get("deliveries", []))
    schedule["deliveries"] = [
        delivery for delivery in schedule.get("deliveries", [])
        if delivery.get("item") != item
    ]

    if len(schedule["deliveries"]) == original_count:
        logger.error(f"Item {item} not found in schedule for workflow {workflow_id}")
        raise DataCorruptionError(f"Item {item} not found in schedule for workflow {workflow_id}")

    # Save the updated schedule back to the database
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE master_construction_schedule
                SET schedule_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE workflow_id = ?
            """, (json.dumps(schedule), workflow_id))
            await db.commit()
            logger.info(f"Removed delivery item {item} from workflow {workflow_id}")

    except aiosqlite.Error as e:
        # Database connection errors - retryable
        logger.warning(f"Database error removing delivery item (retryable): {e}")
        raise DatabaseError(f"Failed to remove delivery item: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error removing delivery item: {e}")
        raise DatabaseError(f"Unexpected error removing delivery item: {e}") from e

async def update_project_end_date_for_workflow(workflow_id: str, new_end_date: str) -> None:
    """
    Update the end date for the project in the construction schedule for a specific workflow.

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If schedule not found (non-retryable)
    """
    # Get the current schedule (may raise DatabaseError or DataCorruptionError)
    schedule = await get_schedule_for_workflow(workflow_id)
    if schedule is None:
        logger.error(f"No schedule found for workflow {workflow_id}")
        raise DataCorruptionError(f"No schedule found for workflow {workflow_id}")

    # Update the project end date in both the JSON and the dedicated column
    schedule["project"]["end_date"] = new_end_date

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE master_construction_schedule
                SET project_end_date = ?, schedule_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE workflow_id = ?
            """, (new_end_date, json.dumps(schedule), workflow_id))
            await db.commit()
            logger.info(f"Updated end date for project in workflow {workflow_id}")

    except aiosqlite.Error as e:
        # Database connection errors - retryable
        logger.warning(f"Database error updating project end date (retryable): {e}")
        raise DatabaseError(f"Failed to update project end date: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error updating project end date: {e}")
        raise DatabaseError(f"Unexpected error updating project end date: {e}") from e


async def create_procurement_item(
    workflow_id: str,
    item: str,
    status: str,
    eta: Optional[str] = None,
    date_arrived: Optional[str] = None,
    purchase_order_id: Optional[str] = None
) -> None:
    """
    Create a new procurement item for tracking through the workflow.

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name (e.g., "Steel Beams")
        status: Current status of the item
        eta: Optional estimated time of arrival
        date_arrived: Optional date the item arrived
        purchase_order_id: Optional purchase order ID

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If input data is invalid (non-retryable)
    """
    # Input validation - non-retryable errors
    if not workflow_id or not isinstance(workflow_id, str):
        raise DataCorruptionError("Invalid workflow_id: must be a non-empty string")

    if not item or not isinstance(item, str):
        raise DataCorruptionError("Invalid item: must be a non-empty string")

    if not status or not isinstance(status, str):
        raise DataCorruptionError("Invalid status: must be a non-empty string")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO procurement_items
                (workflow_id, item, status, eta, date_arrived, purchase_order_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                workflow_id,
                item,
                status,
                eta,
                date_arrived,
                purchase_order_id
            ))
            await db.commit()
            logger.info(f"Created procurement item for workflow {workflow_id}: {item} with status {status}")

    except aiosqlite.IntegrityError as e:
        # Data constraint violation - don't retry
        logger.error(f"Data integrity error: {e}")
        raise DataCorruptionError(f"Data integrity error: {e}") from e

    except aiosqlite.Error as e:
        # Database connection/lock errors - retryable
        logger.warning(f"Database error creating procurement item (retryable): {e}")
        raise DatabaseError(f"Failed to create procurement item: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error creating procurement item: {e}")
        raise DatabaseError(f"Unexpected error creating procurement item: {e}") from e


async def update_procurement_item(
    workflow_id: str,
    item: str,
    status: Optional[str] = None,
    eta: Optional[str] = None,
    date_arrived: Optional[str] = None,
    purchase_order_id: Optional[str] = None
) -> None:
    """
    Update a procurement item's fields. Only updates fields that are provided.

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name (e.g., "Steel Beams")
        status: Optional new status
        eta: Optional new estimated time of arrival
        date_arrived: Optional new arrival date
        purchase_order_id: Optional new purchase order ID

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If workflow_id is invalid or item not found (non-retryable)
    """
    # Input validation - non-retryable errors
    if not workflow_id or not isinstance(workflow_id, str):
        raise DataCorruptionError("Invalid workflow_id: must be a non-empty string")

    if not item or not isinstance(item, str):
        raise DataCorruptionError("Invalid item: must be a non-empty string")

    # Build dynamic update query based on provided fields
    update_fields = []
    params = []

    if status is not None:
        update_fields.append("status = ?")
        params.append(status)

    if eta is not None:
        update_fields.append("eta = ?")
        params.append(eta)

    if date_arrived is not None:
        update_fields.append("date_arrived = ?")
        params.append(date_arrived)

    if purchase_order_id is not None:
        update_fields.append("purchase_order_id = ?")
        params.append(purchase_order_id)

    if not update_fields:
        logger.warning(f"No fields to update for workflow {workflow_id}")
        return

    # Always update the updated_at timestamp
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([workflow_id, item])

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            query = f"""
                UPDATE procurement_items
                SET {', '.join(update_fields)}
                WHERE workflow_id = ? AND item = ?
            """
            cursor = await db.execute(query, params)

            if cursor.rowcount == 0:
                logger.error(f"No procurement item found for workflow {workflow_id} with item {item}")
                raise DataCorruptionError(f"No procurement item found for workflow {workflow_id} with item {item}")

            await db.commit()
            logger.info(f"Updated procurement item for workflow {workflow_id}")

    except DataCorruptionError:
        # Re-raise data corruption errors
        raise

    except aiosqlite.Error as e:
        # Database connection errors - retryable
        logger.warning(f"Database error updating procurement item (retryable): {e}")
        raise DatabaseError(f"Failed to update procurement item: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error updating procurement item: {e}")
        raise DatabaseError(f"Unexpected error updating procurement item: {e}") from e


async def delete_procurement_item(workflow_id: str, item: str) -> None:
    """
    Delete a procurement item from the database.

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name (e.g., "Steel Beams")

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If workflow_id is invalid or item not found (non-retryable)
    """
    # Input validation - non-retryable errors
    if not workflow_id or not isinstance(workflow_id, str):
        raise DataCorruptionError("Invalid workflow_id: must be a non-empty string")

    if not item or not isinstance(item, str):
        raise DataCorruptionError("Invalid item: must be a non-empty string")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                DELETE FROM procurement_items
                WHERE workflow_id = ? AND item = ?
            """, (workflow_id, item))

            if cursor.rowcount == 0:
                logger.error(f"No procurement item found for workflow {workflow_id} with item {item}")
                raise DataCorruptionError(f"No procurement item found for workflow {workflow_id} with item {item}")

            await db.commit()
            logger.info(f"Deleted procurement item for workflow {workflow_id}")

    except DataCorruptionError:
        # Re-raise data corruption errors
        raise

    except aiosqlite.Error as e:
        # Database connection errors - retryable
        logger.warning(f"Database error deleting procurement item (retryable): {e}")
        raise DatabaseError(f"Failed to delete procurement item: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error deleting procurement item: {e}")
        raise DatabaseError(f"Unexpected error deleting procurement item: {e}") from e


async def get_procurement_item_by_name(workflow_id: str, item: str) -> Optional[dict]:
    """
    Retrieve a procurement item for a specific workflow and item name.

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name (e.g., "Steel Beams")

    Returns:
        The procurement item dict or None if not found

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
        DataCorruptionError: If input validation fails (non-retryable)
    """
    # Input validation - non-retryable errors
    if not workflow_id or not isinstance(workflow_id, str):
        raise DataCorruptionError("Invalid workflow_id: must be a non-empty string")

    if not item or not isinstance(item, str):
        raise DataCorruptionError("Invalid item: must be a non-empty string")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT workflow_id, item, status, eta, date_arrived, purchase_order_id, created_at, updated_at
                FROM procurement_items
                WHERE workflow_id = ? AND item = ?
            """, (workflow_id, item)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "workflow_id": row["workflow_id"],
                        "item": row["item"],
                        "status": row["status"],
                        "eta": row["eta"],
                        "date_arrived": row["date_arrived"],
                        "purchase_order_id": row["purchase_order_id"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                return None

    except DataCorruptionError:
        # Re-raise data corruption errors
        raise

    except aiosqlite.Error as e:
        # Database connection errors - retryable
        logger.warning(f"Database error retrieving procurement item (retryable): {e}")
        raise DatabaseError(f"Failed to retrieve procurement item: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error retrieving procurement item: {e}")
        raise DatabaseError(f"Unexpected error retrieving procurement item: {e}") from e


async def get_all_procurement_items() -> list[dict]:
    """
    Retrieve all procurement items from the database.

    Returns:
        List of procurement item dicts

    Raises:
        DatabaseError: If database operation fails (retryable by Temporal)
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT workflow_id, item, status, eta, date_arrived, purchase_order_id, created_at, updated_at
                FROM procurement_items
                ORDER BY created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "workflow_id": row["workflow_id"],
                        "item": row["item"],
                        "status": row["status"],
                        "eta": row["eta"],
                        "date_arrived": row["date_arrived"],
                        "purchase_order_id": row["purchase_order_id"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ]

    except aiosqlite.Error as e:
        # Database connection errors - retryable
        logger.warning(f"Database error retrieving all procurement items (retryable): {e}")
        raise DatabaseError(f"Failed to retrieve all procurement items: {e}") from e

    except Exception as e:
        # Unexpected error - treat as retryable
        logger.error(f"Unexpected error retrieving all procurement items: {e}")
        raise DatabaseError(f"Unexpected error retrieving all procurement items: {e}") from e