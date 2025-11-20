from __future__ import annotations

import json
import uuid
import asyncio
from datetime import datetime, timedelta

from temporalio import activity
from temporalio.exceptions import ApplicationError

from project.data.database import (
    DatabaseError,
    DataCorruptionError,
    create_procurement_item,
    delete_procurement_item,
    update_procurement_item,
    get_all_procurement_items,
    get_schedule_for_workflow,
    create_schedule_for_workflow,
    get_procurement_item_by_name,
    remove_delivery_item_for_workflow,
    update_project_end_date_for_workflow,
    update_delivery_date_for_item_for_workflow,
)
from project.models.events import (
    SubmitalApprovalEvent,
    ShipmentDepartedFactoryEvent,
)
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

@activity.defn
async def issue_purchase_order(event: SubmitalApprovalEvent) -> str:
    """
    Issues a purchase order for construction materials.

    Call this when:
    - A submittal is approved (Submittal_Approved event)
    - Human feedback requests reissuing a purchase order
    """
    uuid_purchase_order = str(uuid.uuid4())
    # wait for 5 seconds as if we were calling an API to issue a purchase order
    await asyncio.sleep(5)
    logger.info(f"Issuing purchase order: {event}")
    logger.info(f"Purchase order ID: {uuid_purchase_order}")

    return f"Successfully issued purchase order with ID: {uuid_purchase_order}"  

@activity.defn
async def flag_potential_issue(event: ShipmentDepartedFactoryEvent) -> str:
    """
    Flags a potential issue with a delivery date.

    Call this when:
    - A shipment departure creates timeline concerns (Shipment_Departed_Factory event)
    - When ETA = required date and there is zero buffer
    - Human feedback identifies a potential delivery issue
    """
    logger.info(f"Flagging potential issue: {event}")
    logger.info(f"Potential issue flagged with delivery date: {event.eta}")
    # imagine this is a call to an API to flag a potential issue, perhaps a notification to a team member
    await asyncio.sleep(1)
    return f"Potential issue flagged with delivery date: {event.eta}"

@activity.defn
async def notify_team_shipment_arrived(event: ShipmentDepartedFactoryEvent) -> str:
    """
    Notifies the team that a shipment has arrived.

    Call this when:
    - A shipment arrives at the site (Shipment_Arrived_Site event)
    - Human feedback requests team notification
    """
    logger.info(f"Notifying team that shipment has arrived: {event.item}")
    logger.info(f"Team notification sent for arrival of: {event.item}")
    # imagine this is a call to an API to notify the team that a shipment has arrived, perhaps a notification to a team member
    await asyncio.sleep(1)

    return f"Notifying team that shipment has arrived: {event.item}"

@activity.defn
async def schedule_inspection(event: ShipmentDepartedFactoryEvent) -> str:
    """
    Schedules an inspection for delivered materials.

    Call this when:
    - A shipment arrives at the site (Shipment_Arrived_Site event)
    - Human feedback requests scheduling an inspection
    """
    inspection_date = datetime.now() + timedelta(days=1)
    logger.info(f"Scheduling inspection for: {event.item} on {inspection_date}")
    # imagine this is a call to an API to schedule an inspection
    await asyncio.sleep(1)
    return f"Scheduling inspection for {event.item} on {inspection_date}"



@activity.defn
async def create_master_construction_schedule(workflow_id: str) -> str:
    """
    Creates the master construction schedule for the workflow.

    Call this when:
    - The workflow is created

    Args:
        workflow_id: The Temporal workflow ID

    Raises:
        ApplicationError: Non-retryable if data is invalid
        DatabaseError: Retryable if database connection fails
    """
    logger.info(f"Creating master construction schedule for workflow: {workflow_id}")

    try:
        await create_schedule_for_workflow(workflow_id)
        return "Master construction schedule created for workflow"

    except DataCorruptionError as e:
        # Application error - invalid data, don't retry
        logger.error(f"Data corruption error creating schedule: {e}")
        raise ApplicationError(
            f"Invalid data creating schedule: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error creating schedule (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error creating schedule: {e}")
        raise

@activity.defn
async def get_master_construction_schedule(workflow_id: str) -> str:
    """
    Gets the master construction schedule for the workflow.

    Call this when:
    - You want to get the master construction schedule for the workflow
    - Human feedback requests the master construction schedule

    Returns:
        The master construction schedule for the workflow as JSON string

    Raises:
        ApplicationError: Non-retryable if schedule not found or data corrupted
        DatabaseError: Retryable if database connection fails
    """
    try:
        schedule = await get_schedule_for_workflow(workflow_id)

        if schedule is None:
            # Schedule not found - this is an application error
            logger.error(f"No schedule found for workflow {workflow_id}")
            raise ApplicationError(
                f"No master construction schedule found for workflow {workflow_id}",
                type="ScheduleNotFoundError",
                non_retryable=True
            )

        logger.info(f"Master construction schedule found for workflow: {workflow_id}")
        return json.dumps(schedule)

    except ApplicationError:
        # Re-raise application errors
        raise

    except DataCorruptionError as e:
        # Application error - corrupted data, don't retry
        logger.error(f"Data corruption error retrieving schedule: {e}")
        raise ApplicationError(
            f"Schedule data corrupted: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error retrieving schedule (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error retrieving schedule: {e}")
        raise

@activity.defn
async def update_delivery_date_for_item(workflow_id: str, item: str, new_delivery_date: str) -> str:
    """
    Updates the delivery date for a specific item in the construction schedule.

    Call this when:
    - You want to update the delivery date for a specific item in the construction schedule
    - Human feedback requests updating the delivery date for a specific item

    Args:
        workflow_id: The Temporal workflow ID
        item: The item to update
        new_delivery_date: The new delivery date

    Raises:
        ApplicationError: Non-retryable if schedule/item not found
        DatabaseError: Retryable if database connection fails
    """
    logger.info(f"Updating delivery date for item: {item} to {new_delivery_date}")

    try:
        await update_delivery_date_for_item_for_workflow(workflow_id, item, new_delivery_date)
        return f"Delivery date updated for item: {item} to {new_delivery_date}"

    except DataCorruptionError as e:
        # Application error - schedule or item not found, don't retry
        logger.error(f"Data corruption error updating delivery date: {e}")
        raise ApplicationError(
            f"Failed to update delivery date: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error updating delivery date (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error updating delivery date: {e}")
        raise

@activity.defn
async def remove_delivery_item(workflow_id: str, item: str) -> str:
    """
    Removes a delivery item from the construction schedule.

    Call this when:
    - You want to remove a delivery item from the construction schedule
    - Human feedback requests removing a delivery item

    Args:
        workflow_id: The Temporal workflow ID
        item: The item to remove

    Raises:
        ApplicationError: Non-retryable if schedule/item not found
        DatabaseError: Retryable if database connection fails
    """
    logger.info(f"Removing delivery item: {item}")

    try:
        await remove_delivery_item_for_workflow(workflow_id, item)
        return f"Delivery item removed from construction schedule: {item}"

    except DataCorruptionError as e:
        # Application error - schedule or item not found, don't retry
        logger.error(f"Data corruption error removing delivery item: {e}")
        raise ApplicationError(
            f"Failed to remove delivery item: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error removing delivery item (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error removing delivery item: {e}")
        raise

@activity.defn
async def update_project_end_date(workflow_id: str, new_end_date: str) -> str:
    """
    Updates the end date for the project in the construction schedule.

    Call this when:
    - You want to update the end date for the project in the construction schedule
    - Human feedback requests updating the end date for the project

    Args:
        workflow_id: The Temporal workflow ID
        new_end_date: The new end date for the project

    Raises:
        ApplicationError: Non-retryable if schedule not found
        DatabaseError: Retryable if database connection fails
    """
    logger.info(f"Updating end date for project to: {new_end_date}")

    try:
        await update_project_end_date_for_workflow(workflow_id, new_end_date)
        return f"End date updated for project: {new_end_date}"

    except DataCorruptionError as e:
        # Application error - schedule not found, don't retry
        logger.error(f"Data corruption error updating project end date: {e}")
        raise ApplicationError(
            f"Failed to update project end date: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error updating project end date (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error updating project end date: {e}")
        raise


@activity.defn
async def create_procurement_item_activity(
    workflow_id: str,
    item: str,
    status: str,
    eta: str | None = None,
    date_arrived: str | None = None,
    purchase_order_id: str | None = None
) -> str:
    """
    Creates a new procurement item for tracking through the workflow.

    Call this when:
    - A submittal is approved (Submittal_Approved event) - automatically after submittal approval
    - Human feedback requests creating a new procurement item

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name (e.g., "Steel Beams")
        status: Current status of the item (e.g., "submittal_approved")
        eta: Optional estimated time of arrival
        date_arrived: Optional date the item arrived
        purchase_order_id: Optional purchase order ID

    Raises:
        ApplicationError: Non-retryable if data is invalid
        DatabaseError: Retryable if database connection fails
    """
    logger.info(f"Creating procurement item for workflow {workflow_id}: {item} with status {status}")

    try:
        await create_procurement_item(
            workflow_id=workflow_id,
            item=item,
            status=status,
            eta=eta,
            date_arrived=date_arrived,
            purchase_order_id=purchase_order_id
        )
        return f"Procurement item created: {item} with status {status}"

    except DataCorruptionError as e:
        # Application error - invalid data, don't retry
        logger.error(f"Data corruption error creating procurement item: {e}")
        raise ApplicationError(
            f"Invalid data creating procurement item: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error creating procurement item (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error creating procurement item: {e}")
        raise


@activity.defn
async def update_procurement_item_activity(
    workflow_id: str,
    item: str,
    status: str | None = None,
    eta: str | None = None,
    date_arrived: str | None = None,
    purchase_order_id: str | None = None
) -> str:
    """
    Updates a procurement item's fields.

    Call this when:
    - Any event occurs that changes the item's status (e.g., shipment departed, arrived, inspection scheduled/failed/passed)
    - Human feedback requests updating the procurement item
    - Purchase order is issued
    - ETA is updated
    - Item arrives at site

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name (e.g., "Steel Beams")
        status: Optional new status
        eta: Optional new estimated time of arrival
        date_arrived: Optional new arrival date
        purchase_order_id: Optional new purchase order ID

    Raises:
        ApplicationError: Non-retryable if workflow_id invalid or item not found
        DatabaseError: Retryable if database connection fails
    """
    logger.info(f"Updating procurement item for workflow {workflow_id}: {item}")

    try:
        await update_procurement_item(
            workflow_id=workflow_id,
            item=item,
            status=status,
            eta=eta,
            date_arrived=date_arrived,
            purchase_order_id=purchase_order_id
        )
        return f"Procurement item updated for workflow {workflow_id}: {item}"

    except DataCorruptionError as e:
        # Application error - item not found or invalid data, don't retry
        logger.error(f"Data corruption error updating procurement item: {e}")
        raise ApplicationError(
            f"Failed to update procurement item: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error updating procurement item (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error updating procurement item: {e}")
        raise


@activity.defn
async def delete_procurement_item_activity(workflow_id: str, item: str) -> str:
    """
    Deletes a procurement item from the database.

    Call this when:
    - Human feedback explicitly requests removing/deleting an item (e.g., "remove the steel beams")
    - Item is no longer needed in the project

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name (e.g., "Steel Beams")

    Raises:
        ApplicationError: Non-retryable if workflow_id invalid or item not found
        DatabaseError: Retryable if database connection fails
    """
    logger.info(f"Deleting procurement item for workflow {workflow_id}: {item}")

    try:
        await delete_procurement_item(workflow_id, item)
        return f"Procurement item deleted for workflow {workflow_id}: {item}"

    except DataCorruptionError as e:
        # Application error - item not found, don't retry
        logger.error(f"Data corruption error deleting procurement item: {e}")
        raise ApplicationError(
            f"Failed to delete procurement item: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error deleting procurement item (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error deleting procurement item: {e}")
        raise


@activity.defn
async def get_procurement_item_by_name_activity(workflow_id: str, item: str) -> str:
    """
    Retrieves a procurement item by workflow ID and item name.

    Call this when:
    - You need to check the status of a specific item
    - You need context about an item before making decisions
    - Human feedback requests information about a specific item

    Args:
        workflow_id: The Temporal workflow ID
        item: The item name (e.g., "Steel Beams")

    Returns:
        JSON string of the procurement item or message if not found

    Raises:
        ApplicationError: Non-retryable if input data is invalid
        DatabaseError: Retryable if database connection fails
    """
    logger.info(f"Getting procurement item for workflow {workflow_id}: {item}")

    try:
        result = await get_procurement_item_by_name(workflow_id, item)

        if result is None:
            return f"No procurement item found for workflow {workflow_id} with item name: {item}"

        return json.dumps(result)

    except DataCorruptionError as e:
        # Application error - invalid input, don't retry
        logger.error(f"Data corruption error getting procurement item: {e}")
        raise ApplicationError(
            f"Invalid input getting procurement item: {e}",
            type="DataCorruptionError",
            non_retryable=True
        ) from e

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error getting procurement item (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error getting procurement item: {e}")
        raise


@activity.defn
async def get_all_procurement_items_activity() -> str:
    """
    Retrieves all procurement items from the database.

    Call this when:
    - You need an overview of all procurement items
    - You need to check the status of multiple items
    - Human feedback requests a summary of all items

    Returns:
        JSON string of all procurement items

    Raises:
        DatabaseError: Retryable if database connection fails
    """
    logger.info("Getting all procurement items")

    try:
        results = await get_all_procurement_items()
        return json.dumps(results)

    except DatabaseError as e:
        # Platform error - database connection issue, let Temporal retry
        logger.warning(f"Database error getting all procurement items (will retry): {e}")
        raise  # Let Temporal retry with activity retry policy

    except Exception as e:
        # Unexpected error - log and let Temporal retry
        logger.error(f"Unexpected error getting all procurement items: {e}")
        raise