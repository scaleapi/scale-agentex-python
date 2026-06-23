"""ACP server for the Temporal Claude Code tutorial.

This file is intentionally thin. When ``acp_type="async"`` is combined
with ``TemporalACPConfig``, FastACP auto-wires:

    HTTP task/create       -> @workflow.run on the workflow class
    HTTP task/event/send   -> @workflow.signal(SignalName.RECEIVE_EVENT)
    HTTP task/cancel       -> workflow cancellation via the Temporal client

The actual agent code lives in ``project/workflow.py`` and is executed by
the Temporal worker (``project/run_worker.py``), not by this HTTP process.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from agentex.lib.types.fastacp import TemporalACPConfig
from agentex.lib.sdk.fastacp.fastacp import FastACP

acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
    ),
)
