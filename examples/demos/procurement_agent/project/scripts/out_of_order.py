#!/usr/bin/env python
"""
Out-of-order events demo script - tests agent's ability to handle duplicate/out-of-order signals.
Sends a submittal approval event again after shipment arrives but before inspection,
to verify the agent recognizes it already happened and ignores the duplicate.
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
EVENT_DELAY = 3
# Longer delay after duplicate to observe how agent handles it
POST_DUPLICATE_DELAY = 10


async def send_out_of_order_events(workflow_id: str):
    """Send events with a duplicate submittal approval after shipment arrives."""

    # Connect to Temporal
    temporal_url = environment_variables.TEMPORAL_ADDRESS or "localhost:7233"
    client = await Client.connect(temporal_url)

    # Get handle to the workflow
    handle = client.get_workflow_handle(workflow_id)

    # Flooring Materials - will PASS inspection, but with duplicate submittal event
    # Required by: 2026-04-01, Buffer: 3 days (so buffer deadline is 2026-03-29)
    # Arriving on 2026-03-20 (12 days early - well within buffer, no warnings)
    events = [
        # 1. Normal: Submittal approved
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="Flooring Materials",
            document_name="Flooring Materials Submittal.pdf",
            document_url="/submittal_approval.pdf"
        ),
        # 2. Normal: Shipment departs
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="Flooring Materials",
            eta=datetime(2026, 3, 20, 13, 15),
            date_departed=datetime(2026, 3, 13, 11, 30),
            location_address="218 W 18th St, New York, NY 10011"
        ),
        # 3. Normal: Shipment arrives
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="Flooring Materials",
            date_arrived=datetime(2026, 3, 20, 12, 45),
            location_address="650 Townsend St, San Francisco, CA 94103"
        ),
        # 4. OUT OF ORDER: Duplicate submittal approval (should be ignored)
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="Flooring Materials",
            document_name="Flooring Materials Submittal.pdf",
            document_url="/submittal_approval.pdf"
        ),
        # 5. Normal: Inspection passes
        InspectionPassedEvent(
            event_type=EventType.INSPECTION_PASSED,
            item="Flooring Materials",
            inspection_date=datetime(2026, 3, 21, 15, 30),
            document_name="Flooring Materials Inspection Report.pdf",
            document_url="/inspection_passed.pdf"
        )
    ]

    event_labels = [
        "Submittal Approved (initial)",
        "Shipment Departed",
        "Shipment Arrived",
        "Submittal Approved (DUPLICATE - should be ignored)",
        "Inspection Passed"
    ]

    print(f"Connected to workflow: {workflow_id}")
    print("=" * 60)
    print("OUT-OF-ORDER DEMO: Testing duplicate event handling")
    print(f"Event delay: {EVENT_DELAY}s")
    print("=" * 60)

    print(f"\n{'=' * 60}")
    print("Processing: Flooring Materials (with duplicate submittal)")
    print("=" * 60)

    for i, (event, label) in enumerate(zip(events, event_labels), 1):
        is_duplicate = (i == 4)

        print(f"\n[{i}/5] Sending: {label}")
        print(f"  Event Type: {event.event_type.value}")
        print(f"  Item: {event.item}")

        if is_duplicate:
            print(f"  ⚠️  This is a DUPLICATE event - agent should recognize and ignore")

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

            # Use longer delay after duplicate to observe handling
            if is_duplicate:
                print(f"  ⏳ Waiting {POST_DUPLICATE_DELAY}s to observe duplicate handling...")
                await asyncio.sleep(POST_DUPLICATE_DELAY)
            else:
                await asyncio.sleep(EVENT_DELAY)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            logger.error(f"Failed to send event: {e}")

    print("\n" + "=" * 60)
    print("Out-of-order demo complete!")
    print("The agent should have recognized the duplicate submittal")
    print("approval and ignored it. Check the UI to verify.")
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
            print("\nUsage: python out_of_order.py [workflow_id]")
            return

    try:
        await send_out_of_order_events(workflow_id)
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
