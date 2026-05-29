"""OpenAI Agents SDK local-sandbox agent definition (async, non-Temporal).

This mirrors the Pydantic AI tutorial (110): the agent is the boundary between
this module and the API layer (acp.py). The difference is the runtime — here we
use the OpenAI Agents SDK ``SandboxAgent`` together with the **local** sandbox
backend (``UnixLocalSandboxClient``).

The local sandbox runs shell commands ON THE HOST — the agent's own
container/process. There is no Docker, no Temporal, and no remote sandbox
infrastructure. The OpenAI Agents SDK runs its own tool-call loop internally:
when the model decides to run a shell command, the sandbox executes it locally
and feeds the output back to the model until it produces a final answer.
"""

from __future__ import annotations

from datetime import datetime

from agents import Runner, set_tracing_disabled
from agents.sandbox import SandboxAgent, SandboxRunConfig
from agents.run_config import RunConfig
from agents.sandbox.sandboxes.unix_local import (
    UnixLocalSandboxClient,
    UnixLocalSandboxClientOptions,
)

from project.tools import get_capabilities

# Disable the openai-agents SDK's native tracer so it doesn't ship traces to
# api.openai.com using OPENAI_API_KEY (which may be a gateway/proxy key and would
# 401). Agentex tracing still runs via the tracing manager configured in acp.py.
set_tracing_disabled(True)

MODEL_NAME = "gpt-4o-mini"
INSTRUCTIONS = """You are a local sandbox assistant.

Current date and time: {timestamp}

You have access to shell tools that run real commands on the local machine.

Guidelines:
- ALWAYS use the shell tools to actually run commands — never guess or make up
  output. If the user asks for the Python version, run `python3 --version`. If
  they ask to list files, run `ls`. If they ask you to compute something, use
  `python3 -c "..."`.
- Run the minimal command(s) needed to answer the question.
- Report the real command output back to the user, concisely.
"""


def create_agent() -> SandboxAgent:
    """Build and return the OpenAI Agents SDK sandbox agent.

    The agent is granted shell capabilities (see ``project.tools``). The actual
    sandbox backend (where the shell commands run) is supplied at run time via
    the ``RunConfig`` returned by ``create_run_config``.
    """
    return SandboxAgent(
        name="Local Sandbox Assistant",
        model=MODEL_NAME,
        instructions=INSTRUCTIONS.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        capabilities=get_capabilities(),
    )


def create_run_config() -> RunConfig:
    """Build the RunConfig that points the agent at the LOCAL sandbox backend.

    ``UnixLocalSandboxClient`` (backend_id="unix_local") runs shell commands on
    the host — the agent's own process — so no Docker or remote infra is needed.
    """
    return RunConfig(
        sandbox=SandboxRunConfig(
            client=UnixLocalSandboxClient(),
            options=UnixLocalSandboxClientOptions(),
        )
    )


async def run_agent(input_list: list) -> "Runner":
    """Run the sandbox agent over the conversation so far and return the result.

    The OpenAI Agents SDK handles the full tool-call loop internally: the model
    issues shell commands, the local sandbox runs them on the host, and the
    output is fed back until the model produces a final answer.

    We pass the full ``input_list`` (prior turns + the new user message) so the
    agent has conversation memory across turns; the caller persists
    ``result.to_input_list()`` back into ``adk.state`` for the next turn.
    """
    agent = create_agent()
    run_config = create_run_config()
    return await Runner.run(agent, input=input_list, run_config=run_config, max_turns=10)
