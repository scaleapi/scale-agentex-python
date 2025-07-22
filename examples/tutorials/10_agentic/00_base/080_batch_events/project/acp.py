"""
WARNING: This tutorial is NOT something that is production ready. It is meant for a demonstration of how to handle a bulk of events in an agentic ACP.

THere are many limitations with trying to do something similar to this. Please see the README.md for more details.
"""
import asyncio
from enum import Enum

from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.acp import SendEventParams, CancelTaskParams, CreateTaskParams
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent

logger = make_logger(__name__)


class TaskCancelledError(Exception):
    pass


class Status(Enum):
    PROCESSING = "processing"
    READY = "ready"
    CANCELLED = "cancelled"


# Create an ACP server
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(type="base")
)

async def process_events_batch(events, task_id: str) -> str:
    """
    Process a batch of events with 2s sleep per event to simulate work.
    Returns the ID of the last processed event.
    """
    if not events:
        return None
    
    logger.info(f"🔄 Processing {len(events)} events: {[e.id for e in events]}")
    
    # Sleep for 2s per event to simulate processing work
    for event in events:
        await asyncio.sleep(5)
        logger.info(f"  INSIDE PROCESSING LOOP - FINISHED PROCESSING EVENT {event.id}")
    
    # Create message showing what was processed
    event_ids = [event.id for event in events]
    message_content = TextContent(
        author="agent",
        content=f"Processed event IDs: {event_ids}"
    )
    
    await adk.messages.create(
        task_id=task_id,
        content=message_content
    )
    
    final_cursor = events[-1].id
    logger.info(f"📝 Message created for {len(events)} events (cursor: {final_cursor})")
    return final_cursor


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams) -> None:
    # For this tutorial, we print the parameters sent to the handler 
    # so you can see where and how task creation is handled
    
    logger.info(f"Task created: {params.task.id} for agent: {params.agent.id}")
    
    # The AgentTaskTracker is automatically created by the server when a task is created
    # Let's verify it exists and log its initial state
    try:
        tracker = await adk.agent_task_tracker.get_by_task_and_agent(
            task_id=params.task.id,
            agent_id=params.agent.id
        )
        logger.info(f"AgentTaskTracker found: {tracker.id}, status: {tracker.status}, last_processed_event_id: {tracker.last_processed_event_id}")
    except Exception as e:
        logger.error(f"Error getting AgentTaskTracker: {e}")
    
    logger.info("Task creation complete")
    return


@acp.on_task_event_send
async def handle_task_event_send(params: SendEventParams) -> None:
    """
    NOTE: See the README.md for a set of limitations as to why this is not the best way to handle events.

    Handle incoming events with batching behavior.
    
    Demonstrates how events arriving during PROCESSING get queued and batched:
    1. Check status - skip if CANCELLED or already PROCESSING  
    2. Set status to PROCESSING
    3. Process events in batches until no more arrive
    4. Set status back to READY
    
    The key insight: while this agent is sleeping 2s per event, new events
    can arrive and will be batched together in the next processing cycle.
    """
    logger.info(f"📥 Received event: {params.event.id}")

    # Get the current AgentTaskTracker state
    try:
        tracker = await adk.agent_task_tracker.get_by_task_and_agent(
            task_id=params.task.id,
            agent_id=params.agent.id
        )
        logger.info(f"Current tracker status: {tracker.status}, cursor: {tracker.last_processed_event_id}")
    except Exception as e:
        logger.error(f"Error getting AgentTaskTracker: {e}")
        return
    
    # Skip if task is cancelled
    if tracker.status == Status.CANCELLED.value:
        logger.error("❌ Task is cancelled. Skipping.")
        return
    
    # Skip if already processing (another pod is handling it)
    if tracker.status == Status.PROCESSING.value:
        logger.info("⏭️  Task is already being processed by another pod. Skipping.")
        return
    
    # LIMITATION - because this is not atomic, it is possible that two different processes will read the value of true
    #   and then both will try to set it to processing. The only way to prevent this is locking, which is not supported
    #   by the agentex server.
    #
    # Options:
    # 1. Implement your own database locking mechanism and provide the agent with the credentials to the database
    # 2. Use Temporal, which will ensure that there is only one workflow execution to be processing at a time (thus not needing a lock anymore)
    # Update status to PROCESSING to claim this processing cycle
    try:
        tracker = await adk.agent_task_tracker.update(
            tracker_id=tracker.id,
            status=Status.PROCESSING.value,
            status_reason="Processing events in batches"
    
        )
        logger.info(f"🔒 Set status to PROCESSING")
    except Exception as e:
        logger.error(f"❌ Failed to set status to PROCESSING (another pod may have claimed it): {e}")
        return
    
    reset_to_ready = True
    try:
        current_cursor = tracker.last_processed_event_id
        # Main processing loop - keep going until no more new events
        while True:
            print(f"\n🔍 Checking for new events since cursor: {current_cursor}")
            
            tracker = await adk.agent_task_tracker.get(tracker_id=tracker.id)
            if tracker.status == Status.CANCELLED.value:
                logger.error("❌ Task is cancelled. Skipping.")
                raise TaskCancelledError("Task is cancelled")
            
            # Get all new events since current cursor
            try:
                print("Listing events since cursor: ", current_cursor)
                new_events = await adk.events.list_events(
                    task_id=params.task.id,
                    agent_id=params.agent.id,
                    last_processed_event_id=current_cursor,
                    limit=100
                )
                
                if not new_events:
                    print("✅ No more new events found - processing cycle complete")
                    break
                
                logger.info(f"🎯 BATCH: Found {len(new_events)} events to process")
                
            except Exception as e:
                logger.error(f"❌ Error collecting events: {e}")
                break
            
            # Process this batch of events (with 2s sleeps)
            try:
                final_cursor = await process_events_batch(new_events, params.task.id)
                
                # Update cursor to mark these events as processed
                await adk.agent_task_tracker.update(
                    tracker_id=tracker.id,
                    last_processed_event_id=final_cursor,
                    status=Status.PROCESSING.value,  # Still processing, might be more
                    status_reason=f"Processed batch of {len(new_events)} events"
                )
                
                current_cursor = final_cursor
                logger.info(f"📊 Updated cursor to: {current_cursor}")
                
            except Exception as e:
                logger.error(f"❌ Error processing events batch: {e}")
                break
    except TaskCancelledError as e:
        logger.error(f"❌ Task cancelled: {e}")
        reset_to_ready = False
    finally:
        if not reset_to_ready:
            return
        
        # Always set status back to READY when done processing
        try:
            await adk.agent_task_tracker.update(
                tracker_id=tracker.id,
                status=Status.READY.value,
                status_reason="Completed event processing - ready for new events"
            )
            logger.info(f"🟢 Set status back to READY - agent available for new events")
        except Exception as e:
            logger.error(f"❌ Error setting status back to READY: {e}")


@acp.on_task_cancel
async def handle_task_canceled(params: CancelTaskParams):
    # For this tutorial, we print the parameters sent to the handler 
    # so you can see where and how task cancellation is handled
    logger.info(f"Hello world! Task canceled: {params.task.id}")
    
    # Update the AgentTaskTracker to reflect cancellation
    try:
        tracker = await adk.agent_task_tracker.get_by_task_and_agent(
            task_id=params.task.id,
            agent_id=params.agent.id
        )
        await adk.agent_task_tracker.update(
            tracker_id=tracker.id,
            status=Status.CANCELLED.value,
            status_reason="Task was cancelled by user"
        )
        logger.info(f"Updated tracker status to cancelled")
    except Exception as e:
        logger.error(f"Error updating tracker on cancellation: {e}")

