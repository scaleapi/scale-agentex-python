import asyncio

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

from project.workflow import ProcurementAgentWorkflow
from project.data.database import init_database
from agentex.lib.utils.debug import setup_debug_if_enabled
from agentex.lib.utils.logging import make_logger
from project.activities.activities import (
    schedule_inspection,
    flag_potential_issue,
    issue_purchase_order,
    remove_delivery_item,
    update_project_end_date,
    notify_team_shipment_arrived,
    update_delivery_date_for_item,
    create_procurement_item_activity,
    delete_procurement_item_activity,
    get_master_construction_schedule,
    update_procurement_item_activity,
    get_all_procurement_items_activity,
    create_master_construction_schedule,
    get_procurement_item_by_name_activity,
)
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import stream_lifecycle_content
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor

environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)


async def main():
    """
    Main worker initialization and execution.
    Handles database initialization and worker startup with error handling.
    """
    try:
        # Setup debug mode if enabled
        setup_debug_if_enabled()

        task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
        if task_queue_name is None:
            raise ValueError("WORKFLOW_TASK_QUEUE is not set")

        # Initialize the database with error handling
        try:
            await init_database()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise RuntimeError(f"Database initialization failed: {e}") from e

        all_activities = get_all_activities() + [stream_lifecycle_content, issue_purchase_order, flag_potential_issue, notify_team_shipment_arrived, schedule_inspection,
        create_master_construction_schedule, get_master_construction_schedule, update_delivery_date_for_item, remove_delivery_item, update_project_end_date,
        create_procurement_item_activity, update_procurement_item_activity, delete_procurement_item_activity,
        get_procurement_item_by_name_activity, get_all_procurement_items_activity]

        context_interceptor = ContextInterceptor()
        streaming_model_provider = TemporalStreamingModelProvider()

        # Create a worker with automatic tracing
        worker = AgentexWorker(
            task_queue=task_queue_name,
            plugins=[OpenAIAgentsPlugin(model_provider=streaming_model_provider)],
            interceptors=[context_interceptor],
        )

        logger.info(f"Starting worker on task queue: {task_queue_name}")

        await worker.run(
            activities=all_activities,
            workflow=ProcurementAgentWorkflow,
        )

    except ValueError as e:
        # Configuration error
        logger.error(f"Configuration error: {e}")
        raise
    except RuntimeError as e:
        # Database or initialization error
        logger.error(f"Initialization error: {e}")
        raise
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error in worker: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 