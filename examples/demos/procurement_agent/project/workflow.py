import os
import json
import asyncio
from typing import Any, Dict, List, override
from datetime import timedelta

from agents import Runner
from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from project.models.events import (
    EventType,
    InspectionFailedEvent,
    InspectionPassedEvent,
    SubmitalApprovalEvent,
    ShipmentArrivedSiteEvent,
    ShipmentDepartedFactoryEvent,
)
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.types.data_content import DataContent
from agentex.types.text_content import TextContent
from project.utils.summarization import (
    should_summarize,
    find_last_summary_index,
    get_messages_to_summarize,
    apply_summary_to_input_list,
)
from project.activities.activities import get_master_construction_schedule, create_master_construction_schedule
from project.agents.procurement_agent import new_procurement_agent
from agentex.lib.environment_variables import EnvironmentVariables
from project.utils.learning_extraction import get_new_wait_for_human_context
from project.agents.summarization_agent import new_summarization_agent
from project.agents.extract_learnings_agent import new_extract_learnings_agent
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.tracing.tracing_processor_manager import (
    add_tracing_processor_config,
)
from agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks import TemporalStreamingHooks

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)

# Setup tracing for SGP (Scale GenAI Platform)
# This enables visibility into your agent's execution in the SGP dashboard
add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SGP_API_KEY", ""),
        sgp_account_id=os.environ.get("SGP_ACCOUNT_ID", ""),
        sgp_base_url=os.environ.get("SGP_BASE_URL"),
    )
)


class TurnInput(BaseModel):
    """Input model for tracing spans."""
    input_list: List[Dict[str, Any]]


class TurnOutput(BaseModel):
    """Output model for tracing spans."""
    final_output: Any


class StateModel(BaseModel):
    """
    State model for preserving conversation history.

    This allows the agent to maintain context throughout the conversation,
    making it possible to reference previous messages and build on the discussion.

    Attributes:
        input_list: The conversation history in OpenAI message format.
        turn_number: Counter for tracking conversation turns (useful for tracing).
    """
    input_list: List[Dict[str, Any]]
    turn_number: int


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class ProcurementAgentWorkflow(BaseWorkflow):
    """
    Minimal async workflow template for AgentEx Temporal agents.
    """
    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._task_id = None
        self._trace_id = None
        self._parent_span_id = None
        self._state = None
        self._workflow_started = False  # Track if agent workflow loop has started
        self.event_queue: asyncio.Queue = asyncio.Queue()   # Events
        self.human_queue: asyncio.Queue = asyncio.Queue()   # Human input
        self.human_input_learnings: list = []
        self.extracted_learning_call_ids: set = set()  # Track which wait_for_human calls we've extracted learnings from

        # Define activity retry policy with exponential backoff
        # Based on Temporal best practices from blog post
        self.activity_retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,  # Exponential backoff
            maximum_interval=timedelta(seconds=120),  # Cap at 2 minutes
            maximum_attempts=5,
            non_retryable_error_types=[
                "DataCorruptionError",
                "ScheduleNotFoundError",
            ]
        )

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    @override
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """
        Handle incoming events from the frontend.

        First event: Triggers the initial agent workflow execution.
        Subsequent events: Feed the wait_for_human tool's human_queue.
        """
        if self._state is None:
            raise ValueError("State is not initialized")

        if params.event.content is None:
            workflow.logger.warning("Received event with no content")
            return

        # Display the user's message in the UI
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        # After the first event, all subsequent events are human responses to wait_for_human
        if self._workflow_started:
            # Extract text content and put it in the human_queue for wait_for_human tool
            if isinstance(params.event.content, TextContent):
                await self.human_queue.put(params.event.content.content)

    @workflow.run
    @override
    async def on_task_create(self, params: CreateTaskParams) -> str:
        logger.info(f"Received task create params: {params}")

        self._state = StateModel(input_list=[], turn_number=0)

        self._task_id = params.task.id
        self._trace_id = params.task.id
        self._parent_span_id = params.task.id

        workflow_id = workflow.info().workflow_id

        # Create the master construction schedule with error handling
        try:
            await workflow.execute_activity(
                create_master_construction_schedule,
                workflow_id,
                start_to_close_timeout=timedelta(minutes=5),  # Changed from 10s to 5min
                schedule_to_close_timeout=timedelta(minutes=10),
                retry_policy=self.activity_retry_policy,
            )
            logger.info("Master construction schedule created successfully")

        except ApplicationError as e:
            # Non-retryable application error (invalid data)
            logger.error(f"Failed to create schedule: {e}")
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="Failed to initialize project schedule. Please contact support.",
                ),
            )
            raise  # Fail the workflow

        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error creating schedule: {e}")
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="System error during initialization. Please try creating a new task.",
                ),
            )
            raise

        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content="Welcome to the Procurement Agent! I'll help you manage construction deliveries and schedules. Send events to get started.",
            ),
        )

        # Mark workflow as started - subsequent events will feed the human_queue
        self._workflow_started = True

        while True:
            await workflow.wait_condition(
                lambda: not self.event_queue.empty(),
                timeout=None,
            )

            if not self.event_queue.empty():
                event = await self.event_queue.get()

                await adk.messages.create(task_id=params.task.id, content=DataContent(
                    author="user",
                    data=json.loads(event),
                ))

                self._state.input_list.append({
                    "role": "user",
                    "content": event,
                })

                # Get master construction schedule with error handling
                try:
                    master_construction_schedule = await workflow.execute_activity(
                        get_master_construction_schedule,
                        workflow_id,
                        start_to_close_timeout=timedelta(minutes=2),  # Changed from 10s to 2min
                        schedule_to_close_timeout=timedelta(minutes=5),
                        retry_policy=self.activity_retry_policy,
                    )
                except ApplicationError as e:
                    # Non-retryable error (schedule not found or corrupted)
                    logger.error(f"Failed to retrieve schedule for event processing: {e}")
                    await adk.messages.create(
                        task_id=params.task.id,
                        content=TextContent(
                            author="agent",
                            content="Unable to access project schedule. Please reinitialize the workflow.",
                        ),
                    )
                    continue  # Skip this event, wait for next one

                except Exception as e:
                    # Unexpected error retrieving schedule
                    logger.error(f"Unexpected error retrieving schedule: {e}")
                    await adk.messages.create(
                        task_id=params.task.id,
                        content=TextContent(
                            author="agent",
                            content="Temporary system issue. Retrying event processing...",
                        ),
                    )
                    continue  # Skip this event, wait for next one

                # Increment turn number for tracing
                self._state.turn_number += 1

                # Create a span to track this turn of the conversation
                turn_input = TurnInput(
                    input_list=self._state.input_list,
                )

                # Create agent and execute with error handling
                try:
                    async with adk.tracing.span(
                        trace_id=params.task.id,
                        name=f"Turn {self._state.turn_number}",
                        input=turn_input.model_dump(),
                    ) as span:
                        self._parent_span_id = span.id if span else None

                        procurement_agent = new_procurement_agent(
                            master_construction_schedule=master_construction_schedule,
                            human_input_learnings=self.human_input_learnings
                        )

                        hooks = TemporalStreamingHooks(task_id=params.task.id)

                        # Execute agent with graceful degradation pattern (from temporal-community demos)
                        result = await Runner.run(procurement_agent, self._state.input_list, hooks=hooks)  # type: ignore[arg-type]

                        # Update state with result
                        self._state.input_list = result.to_input_list()  # type: ignore[assignment]
                        logger.info("Successfully processed event")

                        # Set span output for tracing
                        if span:
                            turn_output = TurnOutput(final_output=result.final_output)
                            span.output = turn_output.model_dump()
                    # Extract learnings from NEW wait_for_human calls only (using going backwards approach)
                    try:
                        result_context = get_new_wait_for_human_context(
                            full_conversation=self._state.input_list,
                            extracted_learning_call_ids=self.extracted_learning_call_ids,
                        )

                        if result_context is not None:
                            new_context, call_id = result_context
                            logger.info("Found new wait_for_human call, extracting learning...")

                            # Create extraction agent and run with only the NEW context
                            extract_agent = new_extract_learnings_agent()
                            extraction_result = await Runner.run(extract_agent, new_context, hooks=hooks)  # type: ignore[arg-type]

                            logger.info(f"About to extract learning: {extraction_result.final_output}")
                            # Append the learning and track the call_id
                            learning = extraction_result.final_output
                            if learning:
                                self.human_input_learnings.append(learning)
                                self.extracted_learning_call_ids.add(call_id)
                                logger.info(f"Extracted learning: {learning}")

                    except Exception as e:
                        logger.error(f"Failed to extract learning: {e}")

                    # Check if summarization is needed (after learning extraction)
                    try:
                        if should_summarize(self._state.input_list):
                            logger.info("Token threshold exceeded, starting summarization...")

                            # Find the last summary index
                            last_summary_index = find_last_summary_index(self._state.input_list)

                            # Get messages to summarize (excludes last 10 turns, starts after previous summary)
                            messages_to_summarize, start_index, end_index = get_messages_to_summarize(
                                self._state.input_list,
                                last_summary_index
                            )

                            if messages_to_summarize:
                                logger.info(f"Summarizing {len(messages_to_summarize)} messages...")

                                # Create summarization agent and run
                                summary_agent = new_summarization_agent()
                                summary_result = await Runner.run(summary_agent, messages_to_summarize, hooks=hooks)  # type: ignore[arg-type]

                                summary_text = summary_result.final_output
                                if summary_text:
                                    # Apply summary to input_list
                                    self._state.input_list = apply_summary_to_input_list(
                                        self._state.input_list,
                                        summary_text,
                                        start_index,
                                        end_index
                                    )
                                    logger.info(f"Summarization complete, new input_list length: {len(self._state.input_list)}")
                                else:
                                    logger.warning("Summarization produced no output")
                            else:
                                logger.info("No messages to summarize (not enough turns yet)")

                    except Exception as e:
                        logger.error(f"Failed to summarize conversation: {e}")

                except Exception as e:
                    # Agent execution failed - graceful degradation
                    logger.error(f"Agent execution failed processing event: {e}")

                    # Notify that event couldn't be processed
                    await adk.messages.create(
                        task_id=params.task.id,
                        content=TextContent(
                            author="agent",
                            content="Unable to process this event. The issue has been logged. Please try sending another event.",
                        ),
                    )

                    # Don't crash workflow - continue and wait for next event
                    continue

            if self._complete_task:
                return "Task completed"

    @workflow.signal
    async def complete_task_signal(self) -> None:
        logger.info("Received signal to complete the agent conversation")
        self._complete_task = True

    @workflow.signal
    async def send_event(self, event: str) -> None:
        """
        Receives event strings from external systems with validation.
        Events should be JSON strings with event_type and required fields.
        Example: {"event_type":"Submittal_Approved","item":"Steel Beams"}
        """
        # Validate event is not None or empty
        if not event:
            logger.error("Received empty or None event")
            raise ValueError("Event cannot be empty or None")

        # Validate event is a string
        if not isinstance(event, str):
            logger.error(f"Event must be string, got {type(event)}")
            raise ValueError(f"Event must be a string, received {type(event).__name__}")

        # Validate event length (prevent DoS)
        if len(event) > 50000:  # 50KB limit
            logger.error(f"Event too large: {len(event)} characters")
            raise ValueError(f"Event exceeds maximum size (50KB)")

        # Validate event is valid JSON
        try:
            event_data = json.loads(event)
        except json.JSONDecodeError as e:
            logger.error(f"Event is not valid JSON: {e}")
            raise ValueError(f"Event must be valid JSON: {e}") from e

        # Validate event has required structure
        if not isinstance(event_data, dict):
            logger.error(f"Event JSON must be an object, got {type(event_data)}")
            raise ValueError("Event must be a JSON object")

        # Validate event_type field exists
        if "event_type" not in event_data:
            logger.error("Event missing 'event_type' field")
            raise ValueError("Event must contain 'event_type' field")

        # Validate event_type is one of the allowed types
        event_type_str = event_data["event_type"]
        valid_event_types = [e.value for e in EventType]

        if event_type_str not in valid_event_types:
            logger.error(f"Invalid event_type: {event_type_str}. Valid types: {valid_event_types}")
            raise ValueError(
                f"Invalid event_type '{event_type_str}'. "
                f"Must be one of: {', '.join(valid_event_types)}"
            )

        # Validate event structure based on type using Pydantic models
        try:
            if event_type_str == EventType.SUBMITTAL_APPROVED.value:
                SubmitalApprovalEvent(**event_data)
            elif event_type_str == EventType.SHIPMENT_DEPARTED_FACTORY.value:
                ShipmentDepartedFactoryEvent(**event_data)
            elif event_type_str == EventType.SHIPMENT_ARRIVED_SITE.value:
                ShipmentArrivedSiteEvent(**event_data)
            elif event_type_str == EventType.INSPECTION_FAILED.value:
                InspectionFailedEvent(**event_data)
            elif event_type_str == EventType.INSPECTION_PASSED.value:
                InspectionPassedEvent(**event_data)
            elif event_type_str == EventType.HUMAN_INPUT.value:
                # HUMAN_INPUT doesn't have a specific model, just needs event_type
                pass

        except Exception as e:
            logger.error(f"Event validation failed for {event_type_str}: {e}")
            raise ValueError(f"Invalid event structure for {event_type_str}: {e}") from e

        logger.info(f"Validated event type: {event_type_str}")
        await self.event_queue.put(event)