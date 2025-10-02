import asyncio
from typing import Any, List, override
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from project.shared_models import StateModel, IncomingEventData
from project.workflow_utils import BatchProcessingUtils
from project.custom_activites import (
    REPORT_PROGRESS_ACTIVITY,
    COMPLETE_WORKFLOW_ACTIVITY,
    ReportProgressActivityParams,
    CompleteWorkflowActivityParams,
)
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if not environment_variables.AGENT_NAME:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)


WAIT_TIMEOUT = 300
BATCH_SIZE = 5
MAX_QUEUE_DEPTH = 50


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At030CustomActivitiesWorkflow(BaseWorkflow):
    """
    Simple tutorial workflow demonstrating custom activities with concurrent processing.
    
    Key Learning Points:
    1. Queue incoming events using Temporal signals
    2. Process events in batches when enough arrive
    3. Use asyncio.create_task() for concurrent processing
    4. Execute custom activities from within workflows
    5. Handle workflow completion cleanly
    """
    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._incoming_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._processing_tasks: List[asyncio.Task[Any]] = []
        self._batch_size = BATCH_SIZE
        self._state: StateModel


    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    @override
    async def on_task_event_send(self, params: SendEventParams) -> None:
        if params.event.content is None:
            return
        
        if params.event.content.type == "text":
            if self._incoming_queue.qsize() >= MAX_QUEUE_DEPTH:
                logger.warning(f"Queue is at max depth of {MAX_QUEUE_DEPTH}. Dropping event.")
                if self._state:
                    self._state.total_events_dropped += 1
            else:
                await self._incoming_queue.put(params.event.content)
            return

        elif params.event.content.type == "data":
            received_data = params.event.content.data
            try:
                received_data = IncomingEventData.model_validate(received_data)
            except Exception as e:
                logger.error(f"Error parsing received data: {e}. Dropping event.")
                return
            
            if received_data.clear_queue:
                await BatchProcessingUtils.handle_queue_clear(self._incoming_queue, params.task.id)
            
            if received_data.cancel_running_tasks:
                await BatchProcessingUtils.handle_task_cancellation(self._processing_tasks, params.task.id)
            else:
                logger.info(f"Received IncomingEventData: {received_data} with no known action.")
        else:
            logger.info(f"Received event: {params.event.content} with no action.")
        

    @workflow.run
    @override
    async def on_task_create(self, params: CreateTaskParams) -> None:
        logger.info(f"Received task create params: {params}")
        
        self._state = StateModel()
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"🚀 Starting batch processing! I'll collect events into batches of {self._batch_size} and process them using custom activities. I'll also report progress you as I go..",
            ),
        )

        batch_number = 0

        # Simple event processing loop with progress tracking
        while True:
            # Check for completed tasks and update progress
            self._processing_tasks = await BatchProcessingUtils.update_progress(self._processing_tasks, self._state, params.task.id)
            
            # Wait for enough events to form a batch, or timeout
            try:
                await workflow.wait_condition(
                    lambda: self._incoming_queue.qsize() >= self._batch_size, 
                    timeout=WAIT_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.info(f"⏰ Timeout after {WAIT_TIMEOUT} seconds - ending workflow")
                break

            # We have enough events - start processing them as a batch
            data_to_process: List[Any] = []
            await BatchProcessingUtils.dequeue_pending_data(self._incoming_queue, data_to_process, self._batch_size)
            
            if data_to_process:                
                await adk.messages.create(
                    task_id=params.task.id,
                    content=TextContent(
                        author="agent",
                        content=f"📦 Starting batch #{batch_number} with {len(data_to_process)} events using asyncio.create_task()",
                    ),
                )
                
                # Create concurrent task for this batch - this is the key learning point!
                task = asyncio.create_task(
                    BatchProcessingUtils.process_batch_concurrent(
                        events=data_to_process,
                        batch_number=batch_number,
                        task_id=params.task.id
                    )
                )
                batch_number += 1
                self._processing_tasks.append(task)
                
                logger.info(f"📝 Tutorial Note: Created asyncio.create_task() for batch #{batch_number} to run asynchronously")
                
                # Check progress again immediately to show real-time updates
                self._processing_tasks = await BatchProcessingUtils.update_progress(self._processing_tasks, self._state, params.task.id)
        
        # Process any remaining events that didn't form a complete batch
        if self._incoming_queue.qsize() > 0:
            data_to_process: List[Any] = []
            await BatchProcessingUtils.dequeue_pending_data(self._incoming_queue, data_to_process, self._incoming_queue.qsize())
            
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content=f"🔄 Processing final {len(data_to_process)} events that didn't form a complete batch.",
                ),
            )
            
            # Now, add another batch to process the remaining events
            task = asyncio.create_task(
                BatchProcessingUtils.process_batch_concurrent(
                    events=data_to_process,
                    batch_number=batch_number,
                    task_id=params.task.id
                )
            )
            self._processing_tasks.append(task)
            batch_number += 1

        # Wait for all remaining tasks to complete, with real-time progress updates
        await BatchProcessingUtils.wait_for_remaining_tasks(self._processing_tasks, self._state, params.task.id)
        await workflow.execute_activity(
            REPORT_PROGRESS_ACTIVITY,
            ReportProgressActivityParams(
                num_batches_processed=self._state.num_batches_processed,
                num_batches_failed=self._state.num_batches_failed,
                num_batches_running=0,
                task_id=params.task.id
            ),
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        final_summary = (
            f"✅ Workflow Complete! Final Summary:\n"
            f"• Batches completed successfully: {self._state.num_batches_processed} ✅\n" 
            f"• Batches failed: {self._state.num_batches_failed} ❌\n"
            f"• Total events processed: {self._state.total_events_processed}\n"
            f"• Events dropped (queue full): {self._state.total_events_dropped}\n"
            f"📝 Tutorial completed - you learned how to use asyncio.create_task() with Temporal custom activities!"
        )
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=final_summary
            ),
        )

        await workflow.execute_activity(
            COMPLETE_WORKFLOW_ACTIVITY,
            CompleteWorkflowActivityParams(
                task_id=params.task.id
            ),
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=3)            
        )        

