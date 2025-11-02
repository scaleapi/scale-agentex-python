"""
Workflow Activities Tutorial

This file demonstrates activities used for WORKFLOW ORCHESTRATION, not as agent tools.
These activities handle operations that the workflow controls directly, like:
- Database writes
- Progress reporting
- Email/notification sending
- Batch processing
- External system integration

Key difference from tutorial 020:
- Tutorial 020: Activities AS agent tools (agent decides when to call)
- Tutorial 040: Activities FOR workflow logic (workflow decides when to call)
"""

import asyncio
from temporalio import activity

from agentex.lib import adk
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent

logger = make_logger(__name__)


@activity.defn
async def save_to_database(task_id: str, data: dict) -> str:
    """
    Save data to a database - runs as a Temporal activity.

    In production, this would:
    - Make actual database calls (PostgreSQL, MongoDB, etc.)
    - Handle connection retries automatically via Temporal
    - Be visible in Temporal UI for observability

    For this tutorial, we simulate the database operation.
    """
    logger.info(f"[DATABASE] Saving data for task {task_id}: {data}")

    # Simulate database latency
    await asyncio.sleep(2)

    logger.info(f"[DATABASE] Successfully saved data for task {task_id}")
    return f"Saved {len(data)} fields to database"


@activity.defn
async def send_notification(task_id: str, message: str, channel: str = "email") -> str:
    """
    Send notification via external service - runs as a Temporal activity.

    In production, this would:
    - Call email service APIs (SendGrid, SES, etc.)
    - Send Slack/Discord notifications
    - Trigger webhooks
    - Be automatically retried on failures

    For this tutorial, we simulate the notification and also send to AgentEx UI.
    """
    logger.info(f"[NOTIFICATION] Sending to {channel}: {message}")

    # Simulate API call latency
    await asyncio.sleep(1)

    # Also send to AgentEx UI so user can see it
    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="agent",
            content=f"📧 [{channel.upper()}] {message}",
        ),
    )

    logger.info(f"[NOTIFICATION] Successfully sent to {channel}")
    return f"Notification sent via {channel}"


@activity.defn
async def process_batch(task_id: str, items: list[str], batch_num: int) -> dict:
    """
    Process a batch of items - runs as a Temporal activity.

    In production, this would:
    - Process multiple records
    - Call external APIs in batch
    - Transform/validate data
    - Handle partial failures with retries

    For this tutorial, we simulate batch processing.
    """
    logger.info(f"[BATCH {batch_num}] Processing {len(items)} items")

    # Send progress update to UI
    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="agent",
            content=f"⚙️ Processing batch #{batch_num} with {len(items)} items...",
        ),
    )

    # Simulate processing time
    await asyncio.sleep(3)

    # Send completion update
    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="agent",
            content=f"✅ Batch #{batch_num} complete! Processed {len(items)} items.",
        ),
    )

    logger.info(f"[BATCH {batch_num}] Successfully processed {len(items)} items")

    return {
        "batch_number": batch_num,
        "items_processed": len(items),
        "status": "completed"
    }


@activity.defn
async def generate_report(task_id: str, summary_data: dict) -> str:
    """
    Generate and store a report - runs as a Temporal activity.

    In production, this would:
    - Generate PDF/Excel reports
    - Upload to S3/cloud storage
    - Create dashboard entries
    - Update analytics systems

    For this tutorial, we simulate report generation.
    """
    logger.info(f"[REPORT] Generating report with data: {summary_data}")

    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="agent",
            content="📊 Generating final report...",
        ),
    )

    # Simulate report generation
    await asyncio.sleep(2)

    report_content = f"""
📊 **Workflow Summary Report**

Total Messages: {summary_data.get('total_messages', 0)}
Batches Processed: {summary_data.get('batches_processed', 0)}
Database Saves: {summary_data.get('database_saves', 0)}
Notifications Sent: {summary_data.get('notifications_sent', 0)}

Status: ✅ Complete
"""

    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="agent",
            content=report_content,
        ),
    )

    logger.info(f"[REPORT] Report generated successfully")
    return "report_12345.pdf"
