import os
import sys

from temporalio.contrib.openai_agents import (
    OpenAIAgentsPlugin,
    SandboxClientProvider,
)
from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient

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
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    ContextInterceptor,
)

context_interceptor = ContextInterceptor()
temporal_streaming_model_provider = TemporalStreamingModelProvider()

# Create the ACP server. We register the STANDARD OpenAIAgentsPlugin with:
#   - the streaming model provider (real-time token streaming + persistence)
#   - the LOCAL sandbox backend, registered under the name "local" so the
#     workflow can resolve it via ``temporal_sandbox_client("local")``
# plus the ContextInterceptor that threads task_id through activity headers.
acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        # When deployed to the cluster, the Temporal address is set automatically.
        # For local development, we set the address manually to talk to the local
        # Temporal service set up via docker compose.
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[
            OpenAIAgentsPlugin(
                model_provider=temporal_streaming_model_provider,
                sandbox_clients=[
                    SandboxClientProvider("local", UnixLocalSandboxClient()),
                ],
            )
        ],
        interceptors=[context_interceptor],
    ),
)


# Notice that we don't need to register any handlers when we use type="temporal".
# These handlers are automatically registered when the ACP is created:
#
# @acp.on_task_create        -> the workflow method decorated with @workflow.run
# @acp.on_task_event_send    -> the workflow method decorated with
#                               @workflow.signal(name=SignalName.RECEIVE_EVENT)
# @acp.on_task_cancel        -> handled by the temporal client (cancels the workflow)
