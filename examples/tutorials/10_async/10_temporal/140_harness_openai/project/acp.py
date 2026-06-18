"""ACP server for the Temporal OpenAI Agents harness tutorial.

Thin by design: with ``acp_type="async"`` + ``TemporalACPConfig``, FastACP
auto-wires task/create, task/event/send, and task/cancel onto the workflow.
The agent logic lives in ``project/workflow.py`` (deterministic) and
``project/activities.py`` (the harness-backed LLM run), executed by the worker
in ``project/run_worker.py``.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from agentex.lib.types.fastacp import TemporalACPConfig
from agentex.lib.sdk.fastacp.fastacp import FastACP

# LiteLLM proxy auth: copy LITELLM_API_KEY to OPENAI_API_KEY for OpenAI client
# compatibility, so the same example works behind the Scale LiteLLM gateway.
_litellm_key = os.environ.get("LITELLM_API_KEY")
if _litellm_key and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = _litellm_key

acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
    ),
)
