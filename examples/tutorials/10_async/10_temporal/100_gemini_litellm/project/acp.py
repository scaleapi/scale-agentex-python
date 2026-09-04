import os
from datetime import timedelta

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters
from agents.extensions.models.litellm_provider import LitellmProvider

# === DEBUG SETUP (AgentEx CLI Debug Support) ===
if os.getenv("AGENTEX_DEBUG_ENABLED") == "true":
    import debugpy
    debug_port = int(os.getenv("AGENTEX_DEBUG_PORT", "5679"))
    debugpy.configure(subProcess=False)
    debugpy.listen(debug_port)
    if os.getenv("AGENTEX_DEBUG_WAIT_FOR_ATTACH", "false").lower() == "true":
        debugpy.wait_for_client()
# === END DEBUG SETUP ===

from agentex.lib.types.fastacp import TemporalACPConfig
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor

context_interceptor = ContextInterceptor()

# Create the ACP server
# We use LitellmProvider instead of TemporalStreamingModelProvider
# to enable using Gemini and other models through LiteLLM
acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        # When deployed to the cluster, the Temporal address will automatically be set to the cluster address
        # For local development, we set the address manually to talk to the local Temporal service set up via docker compose
        #
        # We use the OpenAI Agents SDK plugin because Temporal has built-in support for it,
        # handling serialization and activity wrapping automatically. LitellmProvider lets us
        # route to different model providers (like Gemini) while keeping all that infrastructure.
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[OpenAIAgentsPlugin(
            model_params=ModelActivityParameters(
                start_to_close_timeout=timedelta(days=1)
            ),
            model_provider=LitellmProvider(),
        )],
        interceptors=[context_interceptor]
    )
)


# Notice that we don't need to register any handlers when we use type="temporal"
# If you look at the code in agentex.sdk.fastacp.impl.temporal_acp
# You can see that these handlers are automatically registered when the ACP is created

# @acp.on_task_create
# This will be handled by the method in your workflow that is decorated with @workflow.run

# @acp.on_task_event_send
# This will be handled by the method in your workflow that is decorated with @workflow.signal(name=SignalName.RECEIVE_MESSAGE)

# @acp.on_task_cancel
# This does not need to be handled by your workflow.
# It is automatically handled by the temporal client which cancels the workflow directly
