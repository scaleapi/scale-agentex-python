import asyncio
from typing import Any, List

from pydantic import BaseModel
from temporalio import activity

from agentex.lib import adk
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent

logger = make_logger(__name__)


PROCESS_BATCH_EVENTS_ACTIVITY = "process_batch_events"
class ProcessBatchEventsActivityParams(BaseModel):
  events: List[Any]
  batch_number: int


REPORT_PROGRESS_ACTIVITY = "report_progress"
class ReportProgressActivityParams(BaseModel):
  num_batches_processed: int
  num_batches_failed: int
  num_batches_running: int
  task_id: str


COMPLETE_WORKFLOW_ACTIVITY = "complete_workflow"
class CompleteWorkflowActivityParams(BaseModel):
  task_id: str


class CustomActivities:
  def __init__(self):
    self._batch_size = 5


  @activity.defn(name=PROCESS_BATCH_EVENTS_ACTIVITY)
  async def process_batch_events(self, params: ProcessBatchEventsActivityParams) -> bool:
    """
    This activity will take a list of events and process them.
    
    This is a simple example that demonstrates how to:
    1. Create a custom Temporal activity
    2. Accept structured parameters via Pydantic models
    3. Process batched data
    4. Simulate work with async sleep
    5. Return results back to the workflow
    
    In a real-world scenario, you could:
    - Make database calls (batch inserts, updates)
    - Call external APIs (payment processing, email sending)
    - Perform heavy computations (ML model inference, data analysis)
    - Generate reports or files
    - Any other business logic that benefits from Temporal's reliability
    
    The key benefit is that this activity will automatically:
    - Retry on failures (with configurable retry policies)
    - Be durable across worker restarts
    - Provide observability and metrics
    - Handle timeouts and cancellations gracefully
    """
    logger.info(f"[Batch {params.batch_number}] 🚀 Starting to process batch of {len(params.events)} events")

    # Process each event with some simulated work
    for i, event in enumerate(params.events):
      logger.info(f"[Batch {params.batch_number}] 📄 Processing event {i+1}/{len(params.events)}: {event}")
      
      # Simulate processing time - in reality this could be:
      # - Database operations, API calls, file processing, ML inference, etc.
      await asyncio.sleep(2)
      
      logger.info(f"[Batch {params.batch_number}] ✅ Event {i+1} processed successfully")

    logger.info(f"[Batch {params.batch_number}] 🎉 Batch processing complete! Processed {len(params.events)} events")
    
    # Return success - in reality you might return processing results, IDs, stats, etc.
    return True
  
  @activity.defn(name=REPORT_PROGRESS_ACTIVITY)
  async def report_progress(self, params: ReportProgressActivityParams) -> None:
    """
    This activity will report progress to an external system. 

    NORMALLY, this would be a call to an external system to report progress. For example, this could
    be a call to an email service to send an update email to the user.

    In this example, we'll just log the progress to the console.
    """
    logger.info(f"📊 Progress Update - num_batches_processed: {params.num_batches_processed}, num_batches_failed: {params.num_batches_failed}, num_batches_running: {params.num_batches_running}")

    await adk.messages.create(
        task_id=params.task_id,
        content=TextContent(
            author="agent",
            content=f"📊 Progress Update - num_batches_processed: {params.num_batches_processed}, num_batches_failed: {params.num_batches_failed}, num_batches_running: {params.num_batches_running}",
        ),
    )

  @activity.defn(name=COMPLETE_WORKFLOW_ACTIVITY)
  async def complete_workflow(self, params: CompleteWorkflowActivityParams) -> None:
    """
    This activity will complete the workflow.

    Typically here you may do anything like:
    - Send a final email to the user
    - Send a final message to the user
    - Update a job status in a database to completed
    """
    logger.info(f"🎉 Workflow Complete! Task ID: {params.task_id}")

