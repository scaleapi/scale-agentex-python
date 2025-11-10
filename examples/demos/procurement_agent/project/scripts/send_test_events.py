#!/usr/bin/env python
"""
Simple script to automatically send fake events to the workflow.
Just run this script and it will send a few test events to demonstrate the event handling.
"""

import os
import sys
import asyncio
from datetime import datetime

from temporalio.client import Client

from project.models.events import (
    EventType,
    InspectionFailedEvent,
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


async def send_fake_events(workflow_id: str):
    """Send a series of fake events to the workflow."""

    # Connect to Temporal
    temporal_url = environment_variables.TEMPORAL_ADDRESS or "localhost:7233"
    client = await Client.connect(temporal_url)

    # Get handle to the workflow
    handle = client.get_workflow_handle(workflow_id)

    # Define the procurement event flow for Steel Beams (passes inspection)
    # Required by: 2026-02-15, Buffer: 5 days
    # Arriving on 2026-02-10 (5 days early - within buffer)
    steel_beams_events = [
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="Steel Beams"
        ),
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="Steel Beams",
            eta=datetime(2026, 2, 10)
        ),
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="Steel Beams",
            date_arrived=datetime(2026, 2, 10)
        ),
        InspectionPassedEvent(
            event_type=EventType.INSPECTION_PASSED,
            item="Steel Beams",
            inspection_date=datetime(2026, 2, 11)
        )
    ]

    # Define the procurement event flow for HVAC Units (fails inspection)
    # Required by: 2026-03-01, Buffer: 7 days
    # Arriving on 2026-02-22 (7 days early - within buffer)
    hvac_events = [
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="HVAC Units"
        ),
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="HVAC Units",
            eta=datetime(2026, 2, 22)
        ),
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="HVAC Units",
            date_arrived=datetime(2026, 2, 22)
        ),
        InspectionFailedEvent(
            event_type=EventType.INSPECTION_FAILED,
            item="HVAC Units",
            inspection_date=datetime(2026, 2, 23)
        )
    ]

    # Define the procurement event flow for Windows (passes inspection - everything smooth)
    # Required by: 2026-03-15, Buffer: 10 days
    # Arriving on 2026-03-05 (10 days early - within buffer)
    windows_events = [
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="Windows"
        ),
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="Windows",
            eta=datetime(2026, 3, 5)
        ),
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="Windows",
            date_arrived=datetime(2026, 3, 5)
        ),
        InspectionPassedEvent(
            event_type=EventType.INSPECTION_PASSED,
            item="Windows",
            inspection_date=datetime(2026, 3, 6)
        ),
        # Duplicate arrival event to test agent doesn't double-process
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="Windows",
            date_arrived=datetime(2026, 3, 5)
        )
    ]

    # Define the procurement event flow for Flooring Materials (passes inspection - everything smooth)
    # Required by: 2026-04-01, Buffer: 3 days
    # Arriving on 2026-03-29 (3 days early - within buffer)
    flooring_events = [
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="Flooring Materials"
        ),
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="Flooring Materials",
            eta=datetime(2026, 3, 29)
        ),
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="Flooring Materials",
            date_arrived=datetime(2026, 3, 29)
        ),
        InspectionPassedEvent(
            event_type=EventType.INSPECTION_PASSED,
            item="Flooring Materials",
            inspection_date=datetime(2026, 3, 30)
        )
    ]

    # Define the procurement event flow for Electrical Panels (fails inspection)
    # Required by: 2026-04-15, Buffer: 5 days
    # Arriving on 2026-04-10 (5 days early - within buffer)
    # Agent should apply learnings from HVAC Units failure
    electrical_events = [
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="Electrical Panels"
        ),
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="Electrical Panels",
            eta=datetime(2026, 4, 10)
        ),
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="Electrical Panels",
            date_arrived=datetime(2026, 4, 10)
        ),
        InspectionFailedEvent(
            event_type=EventType.INSPECTION_FAILED,
            item="Electrical Panels",
            inspection_date=datetime(2026, 4, 11)
        )
    ]

    # Combine all events
    all_events = [
        ("Steel Beams", steel_beams_events),
        ("HVAC Units", hvac_events),
        ("Windows", windows_events),
        ("Flooring Materials", flooring_events),
        ("Electrical Panels", electrical_events)
    ]

    print(f"Connected to workflow: {workflow_id}")
    print("=" * 60)
    print("Sending procurement events...")
    print("=" * 60)

    for item_name, events in all_events:
        print(f"\n{'=' * 60}")
        print(f"Processing: {item_name}")
        print("=" * 60)

        for i, event in enumerate(events, 1):
            print(f"\n[Event {i}] Sending: {event.event_type.value}")
            print(f"  Item: {event.item}")

            # Show additional details based on event type
            if hasattr(event, 'eta'):
                print(f"  ETA: {event.eta}")
            if hasattr(event, 'date_arrived'):
                print(f"  Date Arrived: {event.date_arrived}")
            if hasattr(event, 'inspection_date'):
                print(f"  Inspection Date: {event.inspection_date}")

            try:
                # Send the event using the send_event signal
                # Convert event to JSON string
                event_data = event.model_dump_json()
                await handle.signal("send_event", event_data)
                print(f"✓ Event sent successfully!")

                # Wait a bit between events so you can see them being processed
                await asyncio.sleep(10)

            except Exception as e:
                print(f"✗ Error sending event: {e}")
                logger.error(f"Failed to send event: {e}")

    print("\n" + "=" * 60)
    print("All events have been sent!")
    print("Check your workflow in the UI to see the processed events.")
    print("=" * 60)


async def main():
    """Main entry point."""

    # Get workflow ID from command line or prompt user
    if len(sys.argv) > 1:
        workflow_id = sys.argv[1]
    else:
        print("Enter the Workflow ID to send events to:")
        print("(You can find this in the AgentEx UI or Temporal dashboard)")
        workflow_id = input("Workflow ID: ").strip()

        if not workflow_id:
            print("Error: Workflow ID is required!")
            print("\nUsage: python send_simple_events.py [workflow_id]")
            return

    try:
        await send_fake_events(workflow_id)
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