"""The claude-code templates run the CLI sandboxed (VULN-3136).

Whoever can reach a template agent's ACP writes the prompt, so the spawned
``claude`` must get read-only tools, a scratch working directory outside the
project (which holds ``.env``), and none of the agent's own secrets.

Each rendered spawn runs in a child interpreter (importing a rendered ACP module
registers global tracing config) against a stub ``claude`` on PATH.
"""

from __future__ import annotations

import os
import sys
import json
import subprocess
from pathlib import Path

import pytest

from agentex.lib.cli.commands.init import TemplateType

from .test_init_templates import _render_project

SPAWN_MODULES = {
    TemplateType.SYNC_CLAUDE_CODE: "project.acp",
    TemplateType.DEFAULT_CLAUDE_CODE: "project.acp",
    TemplateType.TEMPORAL_CLAUDE_CODE: "project.activities",
}

# Records each spawn the rendered module makes, then lets it run the stub.
DRIVER = """
import sys, json, asyncio, importlib

sys.path.insert(0, ".")
module = importlib.import_module(sys.argv[1])
real_exec = asyncio.create_subprocess_exec
spawns = []

async def recording_exec(*args, **kwargs):
    spawns.append({"argv": list(args), "cwd": str(kwargs.get("cwd")), "env": kwargs.get("env")})
    return await real_exec(*args, **kwargs)

asyncio.create_subprocess_exec = recording_exec

async def main():
    for task_id, kwargs in json.loads(sys.argv[2]):
        async for _ in module._spawn_claude("hi", task_id, **kwargs):
            pass

asyncio.run(main())
print(json.dumps(spawns))
"""

STUB_CLAUDE = """#!{python}
import sys
sys.stdin.read()
print('{{"type": "result", "result": "ok"}}')
"""


def _run(tmp_path: Path, template_type: TemplateType, calls: list) -> subprocess.CompletedProcess[str]:
    """Render the template and run its _spawn_claude once per (task_id, kwargs) in calls."""
    project_dir = _render_project(tmp_path, template_type)
    (project_dir / ".env").write_text("DOTENV_SECRET=CANARY-dotenv\n")
    stub = tmp_path / "bin" / "claude"
    stub.parent.mkdir()
    stub.write_text(STUB_CLAUDE.format(python=sys.executable))
    stub.chmod(0o755)
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    env = {
        "PATH": f"{stub.parent}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "USER": "dev",
        "TMPDIR": str(tmp_dir),
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "AGENT_API_KEY": "CANARY-agent-api-key",
        "SGP_API_KEY": "CANARY-sgp-api-key",
        "AGENT_NAME": "my-agent",
        "ACP_URL": "http://localhost",
    }
    # cwd = the project directory, as under `agentex agents run`.
    return subprocess.run(
        [sys.executable, "-c", DRIVER, SPAWN_MODULES[template_type], json.dumps(calls)],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _spawn(tmp_path: Path, template_type: TemplateType, calls: list) -> tuple[Path, Path, list[dict]]:
    result = _run(tmp_path, template_type, calls)
    assert result.returncode == 0, result.stderr
    return tmp_path / "my_agent", (tmp_path / "tmp").resolve(), json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("template_type", list(SPAWN_MODULES))
def test_claude_runs_with_policy_scratch_dir_and_minimal_env(tmp_path: Path, template_type: TemplateType):
    project_dir, tmp_dir, spawns = _spawn(tmp_path, template_type, [["task-1", {}], ["../../escape", {}]])
    first, hostile = spawns
    argv = first["argv"]

    assert argv[0] == "claude"
    # Only read-only tools exist for the model, so no Bash, Write, Edit or WebFetch.
    assert argv[argv.index("--tools") + 1] == "Read,Glob,Grep"
    # Anything that would need approval, such as a Read outside the working directory, is denied.
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    # The developer's settings (allow rules, extra directories, hooks) and MCP servers are ignored.
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert "--strict-mcp-config" in argv
    for widening in ("--add-dir", "--allowedTools", "--allowed-tools", "--dangerously-skip-permissions"):
        assert widening not in argv

    workdir = Path(first["cwd"]).resolve()
    assert workdir.parent == tmp_dir / "agentex-claude-code"
    assert project_dir.resolve() not in (workdir, *workdir.parents)
    # A crafted task id cannot steer the directory out of the scratch root.
    assert Path(hostile["cwd"]).resolve().parent == workdir.parent
    assert hostile["cwd"] != first["cwd"]

    env = first["env"]
    assert set(env) == {"ANTHROPIC_API_KEY", "PATH", "HOME", "USER"}
    assert "CANARY" not in json.dumps(spawns)


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="the shared-temp-dir check is POSIX-only")
@pytest.mark.parametrize("planted", ["link", "world-writable"])
@pytest.mark.parametrize("template_type", list(SPAWN_MODULES))
def test_refuses_a_scratch_root_another_account_could_control(
    tmp_path: Path, template_type: TemplateType, planted: str
):
    # What another account could leave in a shared /tmp before the agent first runs.
    root = tmp_path / "tmp" / "agentex-claude-code"
    root.parent.mkdir()
    if planted == "link":
        root.symlink_to(tmp_path / "my_agent")
    else:
        root.mkdir()
        root.chmod(0o777)

    result = _run(tmp_path, template_type, [["task-1", {}]])

    assert result.returncode != 0
    assert "is not a private directory owned by this user" in result.stderr


def test_temporal_resume_keeps_the_task_workdir(tmp_path: Path):
    calls = [["task-1", {}], ["task-1", {"session_id": "sess-1"}], ["task-2", {}]]
    _, _, (first, resumed, other) = _spawn(tmp_path, TemplateType.TEMPORAL_CLAUDE_CODE, calls)

    assert resumed["argv"][-2:] == ["-r", "sess-1"]
    # The CLI files sessions by working directory, so resume must run where the first turn ran.
    assert resumed["cwd"] == first["cwd"]
    assert other["cwd"] != first["cwd"]
