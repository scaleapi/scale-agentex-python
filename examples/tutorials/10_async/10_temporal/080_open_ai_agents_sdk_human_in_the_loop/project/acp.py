import os
import sys

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

# === DEBUG SETUP (AgentEx CLI Debug Support) ===
if os.getenv("AGENTEX_DEBUG_ENABLED") == "true":
    try:
        import debugpy
        debug_port = int(os.getenv("AGENTEX_DEBUG_PORT", "5679"))
        debug_type = os.getenv("AGENTEX_DEBUG_TYPE", "acp")
        wait_for_attach = os.getenv("AGENTEX_DEBUG_WAIT_FOR_ATTACH", "false").lower() == "true"
        
        # Configure debugpy
        debugpy.configure(subProcess=False)
        debugpy.listen(debug_port)
        
        print(f"🐛 [{debug_type.upper()}] Debug server listening on port {debug_port}")
        
        if wait_for_attach:
            print(f"⏳ [{debug_type.upper()}] Waiting for debugger to attach...")
            debugpy.wait_for_client()
            print(f"✅ [{debug_type.upper()}] Debugger attached!")
        else:
            print(f"📡 [{debug_type.upper()}] Ready for debugger attachment")
            
    except ImportError:
        print("❌ debugpy not available. Install with: pip install debugpy")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Debug setup failed: {e}")
        sys.exit(1)
# === END DEBUG SETUP ===

from agentex.lib.types.fastacp import TemporalACPConfig
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor

# ============================================================================
# STREAMING SETUP: Interceptor + Model Provider
# ============================================================================
# This is where the streaming magic is configured! Two key components:
#
# 1. ContextInterceptor
#    - Threads task_id through activity headers using Temporal's interceptor pattern
#    - Outbound: Reads _task_id from workflow instance, injects into activity headers
#    - Inbound: Extracts task_id from headers, sets streaming_task_id ContextVar
#    - This enables runtime context without forking the Temporal plugin!
#
# 2. TemporalStreamingModelProvider
#    - Returns TemporalStreamingModel instances that read task_id from ContextVar
#    - TemporalStreamingModel.get_response() streams tokens to Redis in real-time
#    - Still returns complete response to Temporal for determinism/replay safety
#    - Uses AgentEx ADK streaming infrastructure (Redis XADD to stream:{task_id})
#
# Together, these enable real-time LLM streaming while maintaining Temporal's
# durability guarantees. No forked components - uses STANDARD OpenAIAgentsPlugin!
context_interceptor = ContextInterceptor()
temporal_streaming_model_provider = TemporalStreamingModelProvider()

# Create the ACP server
# IMPORTANT: We use the STANDARD temporalio.contrib.openai_agents.OpenAIAgentsPlugin
# No forking needed! The interceptor + model provider handle all streaming logic.
#
# Note: ModelActivityParameters with long timeout allows child workflows to wait
# indefinitely for human input without timing out
acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        # When deployed to the cluster, the Temporal address will automatically be set to the cluster address
        # For local development, we set the address manually to talk to the local Temporal service set up via docker compose
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[OpenAIAgentsPlugin(model_provider=temporal_streaming_model_provider)],
        interceptors=[context_interceptor],
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