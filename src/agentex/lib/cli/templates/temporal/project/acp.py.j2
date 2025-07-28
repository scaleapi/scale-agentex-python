import os
import sys

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

from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.fastacp import TemporalACPConfig


# Create the ACP server
acp = FastACP.create(
    acp_type="agentic",
    config=TemporalACPConfig(
        # When deployed to the cluster, the Temporal address will automatically be set to the cluster address
        # For local development, we set the address manually to talk to the local Temporal service set up via docker compose
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
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