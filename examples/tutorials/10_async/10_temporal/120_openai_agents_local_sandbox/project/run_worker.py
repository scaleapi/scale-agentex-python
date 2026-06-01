import asyncio

from temporalio.contrib.openai_agents import (
    OpenAIAgentsPlugin,
    SandboxClientProvider,
)
from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient

from project.workflow import At120OpenaiAgentsLocalSandboxWorkflow
from agentex.lib.utils.debug import setup_debug_if_enabled
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import (
    stream_lifecycle_content,
)
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    ContextInterceptor,
)

environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)


async def main():
    # Setup debug mode if enabled
    setup_debug_if_enabled()

    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    # Register activities. ``stream_lifecycle_content`` powers the streaming
    # lifecycle hooks; the rest are the standard AgentEx activities.
    all_activities = get_all_activities() + [stream_lifecycle_content]

    # ============================================================================
    # STREAMING + SANDBOX SETUP
    # ============================================================================
    # 1. ContextInterceptor threads task_id through activity headers so the
    #    streaming model + hooks know which task to stream/persist to.
    # 2. TemporalStreamingModelProvider returns a model that streams tokens to
    #    Redis in real time while still returning the complete response to
    #    Temporal for determinism / replay safety.
    # 3. SandboxClientProvider registers the LOCAL sandbox backend
    #    (UnixLocalSandboxClient) under the name "local". The workflow resolves
    #    it at run time via ``temporal_sandbox_client("local")``, so the sandbox
    #    tool calls run as durable Temporal activities.
    #
    # We use the STANDARD temporalio.contrib.openai_agents.OpenAIAgentsPlugin —
    # no forked plugin needed.
    context_interceptor = ContextInterceptor()
    temporal_streaming_model_provider = TemporalStreamingModelProvider()

    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[
            OpenAIAgentsPlugin(
                model_provider=temporal_streaming_model_provider,
                sandbox_clients=[
                    SandboxClientProvider("local", UnixLocalSandboxClient()),
                ],
            )
        ],
        interceptors=[context_interceptor],
    )

    await worker.run(
        activities=all_activities,
        workflow=At120OpenaiAgentsLocalSandboxWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
