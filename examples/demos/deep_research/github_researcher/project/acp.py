import os

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.fastacp import TemporalACPConfig

context_interceptor = ContextInterceptor()
streaming_model_provider = TemporalStreamingModelProvider()

# Create the ACP server
acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[OpenAIAgentsPlugin(model_provider=streaming_model_provider)],
        interceptors=[context_interceptor],
    ),
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(acp, host="0.0.0.0", port=8000)
