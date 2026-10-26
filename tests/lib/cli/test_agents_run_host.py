"""`agentex agents run` keeps the unauthenticated local ACP on loopback unless told otherwise (VULN-3136)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from typer.testing import CliRunner

from agentex.lib.cli.debug import DebugMode, DebugConfig
from agentex.lib.cli.commands import agents as agents_command
from agentex.lib.cli.handlers import run_handlers
from agentex.lib.cli.debug.debug_handlers import start_acp_server_debug


@pytest.mark.parametrize(
    ("args", "env", "expected"),
    [
        ([], {}, "127.0.0.1"),
        (["--host", "0.0.0.0"], {}, "0.0.0.0"),
        ([], {"AGENTEX_AGENT_HOST": "0.0.0.0"}, "0.0.0.0"),
    ],
)
def test_run_command_host(monkeypatch: pytest.MonkeyPatch, args: list[str], env: dict[str, str], expected: str):
    monkeypatch.delenv("AGENTEX_AGENT_HOST", raising=False)
    seen: dict[str, Any] = {}
    monkeypatch.setattr(agents_command, "run_agent", lambda **kwargs: seen.update(kwargs))

    result = CliRunner().invoke(agents_command.agents, ["run", "--manifest", "manifest.yaml", *args], env=env)

    assert result.exit_code == 0, result.output
    assert seen["host"] == expected


async def test_acp_server_listens_on_the_given_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
    hosts: list[str] = []

    async def fake_exec(*args: Any, **_kwargs: Any) -> None:
        hosts.append(args[args.index("--host") + 1])

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(run_handlers, "calculate_uvicorn_target_for_local", lambda *_: "project.acp")
    debug_config = DebugConfig(enabled=True, mode=DebugMode.ACP, port=5678, wait_for_attach=False, auto_port=False)

    await run_handlers.start_acp_server(tmp_path / "acp.py", 8000, {}, tmp_path)
    await start_acp_server_debug(tmp_path / "acp.py", 8000, {}, debug_config)
    await run_handlers.start_acp_server(tmp_path / "acp.py", 8000, {}, tmp_path, host="0.0.0.0")

    assert hosts == ["127.0.0.1", "127.0.0.1", "0.0.0.0"]
