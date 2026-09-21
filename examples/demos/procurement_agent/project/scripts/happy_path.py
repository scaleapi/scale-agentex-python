#!/usr/bin/env python
"""
Happy path demo script - shows two items going through successfully.
Both items pass inspection and arrive within time buffers.
"""

import os
import sys
import asyncio
from datetime import datetime

from temporalio.client import Client

from project.models.events import (
    EventType,
    InspectionPassedEvent,
    SubmitalApprovalEvent,
    ShipmentArrivedSiteEvent,
    ShipmentDepartedFactoryEvent,
)
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables

# Set defaults for local development
os.environ.setdefault("AGENT_NAME", "procurement-agent")
os.environ.setdefault("ACP_URL", "http://localhost:8000")
os.environ.setdefault("WORKFLOW_NAME", "procurement-agent")
os.environ.setdefault("WORKFLOW_TASK_QUEUE", "procurement_agent_queue")
os.environ.setdefault("TEMPORAL_ADDRESS", "localhost:7233")

logger = make_logger(__name__)
environment_variables = EnvironmentVariables.refresh()

# Delay between events (seconds)
EVENT_DELAY = 15


async def send_happy_path_events(workflow_id: str):
    """Send happy path events: two items, both pass inspection."""

    # Connect to Temporal
    temporal_url = environment_variables.TEMPORAL_ADDRESS or "localhost:7233"
    client = await Client.connect(temporal_url)

    # Get handle to the workflow
    handle = client.get_workflow_handle(workflow_id)

    # Item 1: Steel Beams - will PASS inspection
    # Required by: 2026-02-15, Buffer: 5 days
    # Arriving on 2026-02-10 (5 days early - within buffer)
    steel_events = [
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="Steel Beams",
            document_name="Steel Beams Submittal.pdf",
            document_url="/submittal_approval.pdf"
        ),
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="Steel Beams",
            eta=datetime(2026, 2, 10, 14, 30),
            date_departed=datetime(2026, 2, 3, 9, 15),
            location_address="218 W 18th St, New York, NY 10011"
        ),
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="Steel Beams",
            date_arrived=datetime(2026, 2, 10, 15, 45),
            location_address="650 Townsend St, San Francisco, CA 94103"
        ),
        InspectionPassedEvent(
            event_type=EventType.INSPECTION_PASSED,
            item="Steel Beams",
            inspection_date=datetime(2026, 2, 11, 10, 20),
            document_name="Steel Beams Inspection Report.pdf",
            document_url="/inspection_passed.pdf"
        )
    ]

    # Item 2: Windows - will PASS inspection
    # Required by: 2026-03-15, Buffer: 10 days
    # Arriving on 2026-03-05 (10 days early - within buffer)
    windows_events = [
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="Windows",
            document_name="Windows Submittal.pdf",
            document_url="/submittal_approval.pdf"
        ),
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="Windows",
            eta=datetime(2026, 3, 5, 16, 0),
            date_departed=datetime(2026, 2, 20, 8, 30),
            location_address="218 W 18th St, New York, NY 10011"
        ),
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="Windows",
            date_arrived=datetime(2026, 3, 5, 16, 20),
            location_address="650 Townsend St, San Francisco, CA 94103"
        ),
        InspectionPassedEvent(
            event_type=EventType.INSPECTION_PASSED,
            item="Windows",
            inspection_date=datetime(2026, 3, 6, 9, 45),
            document_name="Windows Inspection Report.pdf",
            document_url="/inspection_passed.pdf"
        )
    ]

    all_events = [
        ("Steel Beams", steel_events),
        ("Windows", windows_events),
    ]

    print(f"Connected to workflow: {workflow_id}")
    print("=" * 60)
    print("HAPPY PATH DEMO: Two items, both pass inspection")
    print(f"Event delay: {EVENT_DELAY}s")
    print("=" * 60)

    for item_name, events in all_events:
        print(f"\n{'=' * 60}")
        print(f"Processing: {item_name}")
        print("=" * 60)

        for i, event in enumerate(events, 1):
            print(f"\n[{i}/4] Sending: {event.event_type.value}")
            print(f"  Item: {event.item}")

            if hasattr(event, 'eta'):
                print(f"  ETA: {event.eta}")
            if hasattr(event, 'date_arrived'):
                print(f"  Date Arrived: {event.date_arrived}")
            if hasattr(event, 'inspection_date'):
                print(f"  Inspection Date: {event.inspection_date}")

            try:
                event_data = event.model_dump_json()
                await handle.signal("send_event", event_data)
                print(f"  ✓ Sent!")

                await asyncio.sleep(EVENT_DELAY)

            except Exception as e:
                print(f"  ✗ Error: {e}")
                logger.error(f"Failed to send event: {e}")

    print("\n" + "=" * 60)
    print("Happy path demo complete! Both items passed inspection.")
    print("Check the UI to see processed events.")
    print("=" * 60)


async def main():
    """Main entry point."""

    if len(sys.argv) > 1:
        workflow_id = sys.argv[1]
    else:
        print("Enter Workflow ID:")
        workflow_id = input("Workflow ID: ").strip()

        if not workflow_id:
            print("Error: Workflow ID required!")
            print("\nUsage: python happy_path.py [workflow_id]")
            return

    try:
        await send_happy_path_events(workflow_id)
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. The workflow is running")
        print("2. The workflow ID is correct")
        print("3. Temporal is accessible at", environment_variables.TEMPORAL_ADDRESS)


if __name__ == "__main__":
    asyncio.run(main())
