"""
Event fixtures for eval test cases.

Provides factory functions to create events with configurable parameters.
"""
from typing import Optional
from datetime import datetime, timedelta

from project.models.events import (
    EventType,
    InspectionFailedEvent,
    InspectionPassedEvent,
    SubmitalApprovalEvent,
    ShipmentArrivedSiteEvent,
    ShipmentDepartedFactoryEvent,
)


def create_submittal_approved(item: str) -> SubmitalApprovalEvent:
    """Create a Submittal_Approved event."""
    return SubmitalApprovalEvent(
        event_type=EventType.SUBMITTAL_APPROVED,
        item=item,
        document_name=f"{item} Submittal.pdf",
        document_url=f"/submittals/{item.lower().replace(' ', '_')}.pdf",
    )


def create_shipment_departed(
    item: str,
    eta: datetime,
    date_departed: Optional[datetime] = None,
) -> ShipmentDepartedFactoryEvent:
    """
    Create a Shipment_Departed_Factory event.

    Args:
        item: The item name
        eta: Estimated time of arrival (this is what gets compared to required_by)
        date_departed: When shipment left factory (defaults to 7 days before ETA)
    """
    if date_departed is None:
        date_departed = eta - timedelta(days=7)

    return ShipmentDepartedFactoryEvent(
        event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
        item=item,
        eta=eta,
        date_departed=date_departed,
        location_address="218 W 18th St, New York, NY 10011",
    )


def create_shipment_arrived(
    item: str,
    date_arrived: datetime,
) -> ShipmentArrivedSiteEvent:
    """Create a Shipment_Arrived_Site event."""
    return ShipmentArrivedSiteEvent(
        event_type=EventType.SHIPMENT_ARRIVED_SITE,
        item=item,
        date_arrived=date_arrived,
        location_address="650 Townsend St, San Francisco, CA 94103",
    )


def create_inspection_failed(
    item: str,
    inspection_date: Optional[datetime] = None,
) -> InspectionFailedEvent:
    """Create an Inspection_Failed event."""
    if inspection_date is None:
        inspection_date = datetime.now()

    return InspectionFailedEvent(
        event_type=EventType.INSPECTION_FAILED,
        item=item,
        inspection_date=inspection_date,
        document_name=f"{item} Inspection Report.pdf",
        document_url=f"/inspections/{item.lower().replace(' ', '_')}_failed.pdf",
    )


def create_inspection_passed(
    item: str,
    inspection_date: Optional[datetime] = None,
) -> InspectionPassedEvent:
    """Create an Inspection_Passed event."""
    if inspection_date is None:
        inspection_date = datetime.now()

    return InspectionPassedEvent(
        event_type=EventType.INSPECTION_PASSED,
        item=item,
        inspection_date=inspection_date,
        document_name=f"{item} Inspection Report.pdf",
        document_url=f"/inspections/{item.lower().replace(' ', '_')}_passed.pdf",
    )


# Default schedule reference (matches database.py DEFAULT_SCHEDULE)
SCHEDULE_REFERENCE = {
    "Steel Beams": {"required_by": "2026-02-15", "buffer_days": 5},
    "HVAC Units": {"required_by": "2026-03-01", "buffer_days": 7},
    "Windows": {"required_by": "2026-03-15", "buffer_days": 10},
    "Flooring Materials": {"required_by": "2026-04-01", "buffer_days": 3},
    "Electrical Panels": {"required_by": "2026-04-15", "buffer_days": 5},
}
