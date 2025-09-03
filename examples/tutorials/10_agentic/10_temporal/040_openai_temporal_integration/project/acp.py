import os

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
# you can see that the handlers are automatically registered to forward all ACP events
# to the temporal workflow via the temporal client.

# The temporal workflow is responsible for handling the ACP events and sending responses
# This is handled by the workflow method that is decorated with @workflow.signal(name=SignalName.RECEIVE_EVENT)
