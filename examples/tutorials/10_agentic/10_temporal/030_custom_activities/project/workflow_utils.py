import asyncio
from typing import Any, Dict, List
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from agentex.lib import adk
from project.shared_models import StateModel
from project.custom_activites import (
    REPORT_PROGRESS_ACTIVITY,
    PROCESS_BATCH_EVENTS_ACTIVITY,
    ReportProgressActivityParams,
    ProcessBatchEventsActivityParams,
)
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent

logger = make_logger(__name__)


class BatchProcessingUtils:
    """
    Utility class containing batch processing logic extracted from the main workflow.
    This keeps the workflow clean while maintaining all the same functionality.
    """
    
    @staticmethod
    async def dequeue_pending_data(queue: asyncio.Queue[Any], data_to_process: List[Any], max_items: int) -> None:
        """
        Dequeue exactly the number of items requested, maintaining FIFO order.
        This is much cleaner than dequeuing everything and putting items back.
        """
        items_dequeued = 0
        while items_dequeued < max_items and not queue.empty():
            try:
                item = queue.get_nowait()
                data_to_process.append(item)
                items_dequeued += 1
            except Exception:
                # Queue became empty while we were dequeuing
                break

    @staticmethod
    async def process_batch_concurrent(events: List[Any], batch_number: int, task_id: str) -> Dict[str, Any]:
        """
        Process a single batch using a custom activity.
        This demonstrates how asyncio.create_task() allows multiple batches to run concurrently.
        Returns batch info for state tracking by the main workflow thread.
        """
        try:
            logger.info(f"🚀 Batch #{batch_number}: Starting concurrent processing of {len(events)} events")
            
            # This is the key: calling a custom activity from within the workflow
            await workflow.execute_activity(
                PROCESS_BATCH_EVENTS_ACTIVITY,
                ProcessBatchEventsActivityParams(
                    events=events,
                    batch_number=batch_number
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            await adk.messages.create(
                task_id=task_id,
                content=TextContent(
                    author="agent",
                    content=f"✅ Batch #{batch_number} completed! Processed {len(events)} events using custom activity.",
                ),
            )
            
            logger.info(f"✅ Batch #{batch_number}: Processing completed successfully")
            return {"success": True, "events_processed": len(events), "batch_number": batch_number}
            
        except Exception as e:
            await adk.messages.create(
                task_id=task_id,
                content=TextContent(
                    author="agent",
                    content=f"❌ Batch #{batch_number} failed: {str(e)}",
                ),
            )
            logger.error(f"❌ Batch #{batch_number} failed: {str(e)}")
            return {"success": False, "events_processed": 0, "batch_number": batch_number, "error": str(e)}

    @staticmethod
    async def update_progress(processing_tasks: List[asyncio.Task[Any]], state: StateModel, task_id: str) -> List[asyncio.Task[Any]]:
        """
        Check for completed tasks and update progress in real-time.
        This is key for tutorials - showing progress as things happen!
        
        Returns the updated list of still-running tasks.
        """
        if not processing_tasks:
            return processing_tasks
            
        # Check which tasks have completed
        completed_tasks: List[asyncio.Task[Any]] = []
        still_running: List[asyncio.Task[Any]] = []
        
        for task in processing_tasks:
            if task.done():
                completed_tasks.append(task)
            else:
                still_running.append(task)
        
        # Update state based on completed tasks
        if completed_tasks:
            for task in completed_tasks:
                try:
                    result = await task  # Get the result
                    if isinstance(result, dict) and result.get("success"):
                        # Successful processing - update state
                        state.num_batches_processed += 1
                        state.total_events_processed += result.get("events_processed", 0)
                    else:
                        # Failed processing
                        state.num_batches_failed += 1
                except Exception:
                    # Task failed with exception
                    state.num_batches_failed += 1
            
            await workflow.execute_activity(
                REPORT_PROGRESS_ACTIVITY,
                ReportProgressActivityParams(
                    num_batches_processed=state.num_batches_processed,
                    num_batches_failed=state.num_batches_failed,
                    num_batches_running=len(still_running),
                    task_id=task_id,
                ),
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )                    
        return still_running

    @staticmethod
    async def handle_queue_clear(queue: asyncio.Queue[Any], task_id: str) -> int:
        """
        Handle clearing the event queue and return the number of events cleared.
        """
        num_events = queue.qsize()
        logger.info(f"Clearing queue of size: {num_events}")
        while not queue.empty():
            queue.get_nowait()

        await adk.messages.create(
            task_id=task_id,
            content=TextContent(
                author="agent",
                content=f"I just cleared the queue of events that were received. Total cleared events: {num_events}",
            ),
        )
        return num_events

    @staticmethod
    async def handle_task_cancellation(processing_tasks: List[asyncio.Task[Any]], task_id: str) -> int:
        """
        Handle cancelling all running batch processing tasks.
        Returns the number of tasks cancelled.
        """
        # Simple cancellation for tutorial purposes
        cancelled_count = len([task for task in processing_tasks if not task.done()])
        for task in processing_tasks:
            if not task.done():
                task.cancel()
        
        processing_tasks.clear()
        await adk.messages.create(
            task_id=task_id,
            content=TextContent(
                author="agent",
                content=f"⛔ Cancelled {cancelled_count} running tasks. This shows how asyncio.create_task() tasks can be cancelled!",
            ),
        )
        return cancelled_count

    @staticmethod
    async def wait_for_remaining_tasks(processing_tasks: List[asyncio.Task[Any]], state: Any, task_id: str) -> None:
        """
        Wait for all remaining tasks to complete, with real-time progress updates.
        """
        while processing_tasks:
            await adk.messages.create(
                task_id=task_id,
                content=TextContent(
                    author="agent",
                    content=f"⏳ Waiting for {len(processing_tasks)} remaining batches to complete...",
                ),
            )
            
            # Wait a bit, then update progress
            try:
                await workflow.wait_condition(
                    lambda: not any(task for task in processing_tasks if not task.done()),
                    timeout=10  # Check progress every 10 seconds
                )
                # All tasks are done!
                processing_tasks[:] = await BatchProcessingUtils.update_progress(processing_tasks, state, task_id)
                break
            except asyncio.TimeoutError:
                # Some tasks still running, update progress and continue waiting
                processing_tasks[:] = await BatchProcessingUtils.update_progress(processing_tasks, state, task_id)
                continue