import os
import sys

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor

# === DEBUG SETUP (AgentEx CLI Debug Support) ===
if os.getenv("AGENTEX_DEBUG_ENABLED") == "true":
    try:
        import debugpy

        from agentex.lib.utils.logging import make_logger

        logger = make_logger(__name__)
        debug_port = int(os.getenv("AGENTEX_DEBUG_PORT", "5679"))
        debug_type = os.getenv("AGENTEX_DEBUG_TYPE", "acp")
        wait_for_attach = os.getenv("AGENTEX_DEBUG_WAIT_FOR_ATTACH", "false").lower() == "true"

        # Configure debugpy
        debugpy.configure(subProcess=False)
        debugpy.listen(debug_port)

        logger.info(f"🐛 [{debug_type.upper()}] Debug server listening on port {debug_port}")

        if wait_for_attach:
            logger.info(f"⏳ [{debug_type.upper()}] Waiting for debugger to attach...")
            debugpy.wait_for_client()
            logger.info(f"✅ [{debug_type.upper()}] Debugger attached!")
        else:
            logger.info(f"📡 [{debug_type.upper()}] Ready for debugger attachment")

    except ImportError:
        print("❌ debugpy not available. Install with: pip install debugpy")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Debug setup failed: {e}")
        sys.exit(1)
# === END DEBUG SETUP ===

from agentex.lib.types.fastacp import TemporalACPConfig
from agentex.lib.sdk.fastacp.fastacp import FastACP

context_interceptor = ContextInterceptor()
streaming_model_provider = TemporalStreamingModelProvider()

# Create the ACP server
acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[OpenAIAgentsPlugin(model_provider=streaming_model_provider)],
        interceptors=[context_interceptor]
    )
)