"""ACP server for the Temporal LangGraph agent.

This file is intentionally thin. When ``acp_type="async"`` is combined with
``TemporalACPConfig(type="temporal", ...)``, FastACP auto-wires:

    HTTP task/create       → @workflow.run on the workflow class
    HTTP task/event/send   → @workflow.signal(SignalName.RECEIVE_EVENT)
    HTTP task/cancel       → workflow cancellation via the Temporal client

so we don't define any handlers here. The agent logic lives in
``project/workflow.py`` (the runtime) and ``project/graph.py`` (the LangGraph
graph whose nodes run as Temporal activities), executed by the Temporal worker
(``project/run_worker.py``), not by this HTTP process.

The ``LangGraphPlugin`` is registered here too so the Temporal client started
by FastACP shares the same graph registry as the worker.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from temporalio.contrib.langgraph import LangGraphPlugin

from project.graph import GRAPH_NAME, build_graph
from agentex.lib.types.fastacp import TemporalACPConfig
from agentex.lib.sdk.fastacp.fastacp import FastACP

acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        # When deployed to the cluster, the Temporal address is set automatically.
        # Locally we point at the Temporal service from docker compose.
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[LangGraphPlugin(graphs={GRAPH_NAME: build_graph()})],
    ),
)