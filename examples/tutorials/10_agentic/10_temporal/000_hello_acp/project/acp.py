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
# You can see that these handlers are automatically registered when the ACP is created

# @acp.on_task_create
# This will be handled by the method in your workflow that is decorated with @workflow.run

# @acp.on_task_event_send
# This will be handled by the method in your workflow that is decorated with @workflow.signal(name=SignalName.RECEIVE_MESSAGE)

# @acp.on_task_cancel
# This does not need to be handled by your workflow.
# It is automatically handled by the temporal client which cancels the workflow directly 