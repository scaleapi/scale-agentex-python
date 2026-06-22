"""ACP server for the Temporal harness LangGraph agent.

Follows the ``130_langgraph`` pattern: the Temporal ``LangGraphPlugin`` runs
graph nodes as Temporal activities. The agent logic lives in ``workflow.py``
(the runtime) and ``graph.py`` (the LangGraph graph), executed by the Temporal
worker (``run_worker.py``), not by this HTTP process.

The workflow uses ``emit_langgraph_messages`` to surface turn messages to
AgentEx. That helper is Temporal-specific and is not replaced by the unified
harness here (``UnifiedEmitter`` targets the non-Temporal async/sync channels).
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
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        plugins=[LangGraphPlugin(graphs={GRAPH_NAME: build_graph()})],
    ),
)
