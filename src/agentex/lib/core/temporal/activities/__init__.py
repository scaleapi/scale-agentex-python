from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from scale_gp import SGPClient, SGPClientError

from agentex import AsyncAgentex
from agentex.lib.core.adapters.llm.adapter_litellm import LiteLLMGateway
from agentex.lib.core.adapters.streams.adapter_redis import RedisStreamRepository
from agentex.lib.core.services.adk.acp.acp import ACPService
from agentex.lib.core.services.adk.agent_task_tracker import AgentTaskTrackerService
from agentex.lib.core.services.adk.events import EventsService
from agentex.lib.core.services.adk.messages import MessagesService
from agentex.lib.core.services.adk.providers.litellm import LiteLLMService
from agentex.lib.core.services.adk.providers.openai import OpenAIService
from agentex.lib.core.services.adk.providers.sgp import SGPService
from agentex.lib.core.services.adk.state import StateService
from agentex.lib.core.services.adk.streaming import StreamingService
from agentex.lib.core.services.adk.tasks import TasksService
from agentex.lib.core.services.adk.tracing import TracingService
from agentex.lib.core.services.adk.utils.templating import TemplatingService
from agentex.lib.core.temporal.activities.adk.acp.acp_activities import ACPActivities
from agentex.lib.core.temporal.activities.adk.agent_task_tracker_activities import (
    AgentTaskTrackerActivities,
)
from agentex.lib.core.temporal.activities.adk.events_activities import EventsActivities
from agentex.lib.core.temporal.activities.adk.messages_activities import MessagesActivities
from agentex.lib.core.temporal.activities.adk.providers.litellm_activities import (
    LiteLLMActivities,
)
from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
    OpenAIActivities,
)
from agentex.lib.core.temporal.activities.adk.providers.sgp_activities import SGPActivities
from agentex.lib.core.temporal.activities.adk.state_activities import StateActivities
from agentex.lib.core.temporal.activities.adk.streaming_activities import (
    StreamingActivities,
)
from agentex.lib.core.temporal.activities.adk.tasks_activities import TasksActivities
from agentex.lib.core.temporal.activities.adk.tracing_activities import TracingActivities
from agentex.lib.core.temporal.activities.adk.utils.templating_activities import (
    TemplatingActivities,
)
from agentex.lib.core.tracing import AsyncTracer


def get_all_activities(sgp_client=None):
    """
    Returns a list of all standard activity functions that can be directly passed to worker.run().

    Args:
        sgp_client: Optional SGP client instance. If not provided, SGP activities will not be included.

    Returns:
        list: A list of activity functions ready to be passed to worker.run()
    """
    # Initialize common dependencies
    try:
        sgp_client = SGPClient()
    except SGPClientError:
        sgp_client = None

    llm_gateway = LiteLLMGateway()
    stream_repository = RedisStreamRepository()
    agentex_client = create_async_agentex_client()
    tracer = AsyncTracer(agentex_client)

    # Services

    ## ADK
    streaming_service = StreamingService(
        agentex_client=agentex_client,
        stream_repository=stream_repository,
    )
    messages_service = MessagesService(
        agentex_client=agentex_client,
        streaming_service=streaming_service,
        tracer=tracer,
    )
    events_service = EventsService(
        agentex_client=agentex_client,
        tracer=tracer,
    )
    agent_task_tracker_service = AgentTaskTrackerService(
        agentex_client=agentex_client,
        tracer=tracer,
    )
    state_service = StateService(
        agentex_client=agentex_client,
        tracer=tracer,
    )
    tasks_service = TasksService(
        agentex_client=agentex_client,
        tracer=tracer,
    )
    tracing_service = TracingService(
        tracer=tracer,
    )

    ## ACP
    acp_service = ACPService(
        agentex_client=agentex_client,
        tracer=tracer,
    )

    ## Providers
    litellm_service = LiteLLMService(
        agentex_client=agentex_client,
        llm_gateway=llm_gateway,
        streaming_service=streaming_service,
        tracer=tracer,
    )
    openai_service = OpenAIService(
        agentex_client=agentex_client,
        streaming_service=streaming_service,
        tracer=tracer,
    )
    sgp_service = None
    if sgp_client is not None:
        sgp_service = SGPService(
            sgp_client=sgp_client,
            tracer=tracer,
        )

    ## Utils
    templating_service = TemplatingService(
        tracer=tracer,
    )

    # ADK

    ## Core activities
    messages_activities = MessagesActivities(messages_service=messages_service)
    events_activities = EventsActivities(events_service=events_service)
    agent_task_tracker_activities = AgentTaskTrackerActivities(
        agent_task_tracker_service=agent_task_tracker_service
    )
    state_activities = StateActivities(state_service=state_service)
    streaming_activities = StreamingActivities(streaming_service=streaming_service)
    tasks_activities = TasksActivities(tasks_service=tasks_service)
    tracing_activities = TracingActivities(tracing_service=tracing_service)

    ## ACP
    acp_activities = ACPActivities(acp_service=acp_service)

    ## Providers
    litellm_activities = LiteLLMActivities(litellm_service=litellm_service)
    openai_activities = OpenAIActivities(openai_service=openai_service)
    if sgp_client is not None:
        sgp_activities = SGPActivities(sgp_service=sgp_service)
    else:
        sgp_activities = None

    ## Utils
    templating_activities = TemplatingActivities(templating_service=templating_service)

    # Build list of standard activities
    activities = [
        # Core activities
        ## Messages activities
        messages_activities.create_message,
        messages_activities.update_message,
        messages_activities.create_messages_batch,
        messages_activities.update_messages_batch,
        messages_activities.list_messages,
        ## Events activities
        events_activities.get_event,
        events_activities.list_events,
        ## Agent Task Tracker activities
        agent_task_tracker_activities.get_agent_task_tracker,
        agent_task_tracker_activities.get_agent_task_tracker_by_task_and_agent,
        agent_task_tracker_activities.update_agent_task_tracker,
        ## State activities
        state_activities.create_state,
        state_activities.get_state,
        state_activities.update_state,
        state_activities.delete_state,
        ## Streaming activities
        streaming_activities.stream_update,
        ## Tasks activities
        tasks_activities.get_task,
        tasks_activities.delete_task,
        ## Tracing activities
        tracing_activities.start_span,
        tracing_activities.end_span,
        # ACP activities
        acp_activities.task_create,
        acp_activities.message_send,
        acp_activities.event_send,
        acp_activities.task_cancel,
        # Providers
        ## LiteLLM activities
        litellm_activities.chat_completion,
        litellm_activities.chat_completion_auto_send,
        litellm_activities.chat_completion_stream_auto_send,
        ## OpenAI activities
        openai_activities.run_agent,
        openai_activities.run_agent_auto_send,
        openai_activities.run_agent_streamed_auto_send,
        # Utils
        templating_activities.render_jinja,
    ]

    # SGP activities
    if sgp_client is not None:
        sgp_all_activities = [
            sgp_activities.download_file_content,
        ]
        activities.extend(sgp_all_activities)

    return activities
