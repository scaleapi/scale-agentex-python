#!/usr/bin/env python
"""
Human-in-the-loop demo script - shows an item that fails inspection.
Demonstrates the need for human intervention when inspection fails.
"""

import os
import sys
import asyncio
from datetime import datetime

from temporalio.client import Client

from project.models.events import (
    EventType,
    InspectionFailedEvent,
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
# Longer delay after inspection failure to observe the failure handling
POST_FAILURE_DELAY = 30


async def send_human_in_the_loop_events(workflow_id: str):
    """Send events for one item that fails inspection."""

    # Connect to Temporal
    temporal_url = environment_variables.TEMPORAL_ADDRESS or "localhost:7233"
    client = await Client.connect(temporal_url)

    # Get handle to the workflow
    handle = client.get_workflow_handle(workflow_id)

    # HVAC Units - will FAIL inspection
    # Required by: 2026-03-01, Buffer: 7 days
    # Arriving on 2026-02-15 (14 days early - well within buffer)
    hvac_events = [
        SubmitalApprovalEvent(
            event_type=EventType.SUBMITTAL_APPROVED,
            item="HVAC Units",
            document_name="HVAC Units Submittal.pdf",
            document_url="/submittal_approval.pdf"
        ),
        ShipmentDepartedFactoryEvent(
            event_type=EventType.SHIPMENT_DEPARTED_FACTORY,
            item="HVAC Units",
            eta=datetime(2026, 2, 15, 11, 0),
            date_departed=datetime(2026, 2, 8, 13, 45),
            location_address="218 W 18th St, New York, NY 10011"
        ),
        ShipmentArrivedSiteEvent(
            event_type=EventType.SHIPMENT_ARRIVED_SITE,
            item="HVAC Units",
            date_arrived=datetime(2026, 2, 15, 10, 30),
            location_address="650 Townsend St, San Francisco, CA 94103"
        ),
        InspectionFailedEvent(
            event_type=EventType.INSPECTION_FAILED,
            item="HVAC Units",
            inspection_date=datetime(2026, 2, 16, 14, 15),
            document_name="HVAC Units Inspection Report.pdf",
            document_url="/inspection_failed.pdf"
        )
    ]

    print(f"Connected to workflow: {workflow_id}")
    print("=" * 60)
    print("HUMAN-IN-THE-LOOP DEMO: Item fails inspection")
    print(f"Event delay: {EVENT_DELAY}s")
    print("=" * 60)

    print(f"\n{'=' * 60}")
    print("Processing: HVAC Units (will FAIL inspection)")
    print("=" * 60)

    for i, event in enumerate(hvac_events, 1):
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

            # Use longer delay after inspection failure
            is_last_event = (i == len(hvac_events))
            if is_last_event:
                print(f"\n  ⚠️  INSPECTION FAILED!")
                print(f"  ⏳ Waiting {POST_FAILURE_DELAY}s to observe failure handling...")
                print(f"  💡 Check the UI - agent should request human input")
                await asyncio.sleep(POST_FAILURE_DELAY)
            else:
                await asyncio.sleep(EVENT_DELAY)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            logger.error(f"Failed to send event: {e}")

    print("\n" + "=" * 60)
    print("Human-in-the-loop demo complete!")
    print("The agent should now be waiting for human input to resolve")
    print("the inspection failure. Check the UI to provide input.")
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
            print("\nUsage: python human_in_the_loop.py [workflow_id]")
            return

    try:
        await send_human_in_the_loop_events(workflow_id)
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
