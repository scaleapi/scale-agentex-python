"""The rendered Claude Code scaffold against a real child process.

A fake ``claude`` on PATH stands in for the CLI, so these run offline but
exercise the template's actual subprocess handling: the stdout line limit
and the SIGTERM-then-SIGKILL shutdown.
"""

from __future__ import annotations

import sys
import time
import types
import asyncio
import importlib.util
from pathlib import Path

import pytest

from agentex.lib.core.tracing import tracing_processor_manager
from agentex.lib.cli.commands.init import TemplateType, get_project_context, create_project_structure

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="needs POSIX signals")

LONG_LINE_CHARS = 100_000
FAST_TERMINATE_SECONDS = 0.5
SHUTDOWN_BUDGET_SECONDS = 10.0

FAKE_CLAUDE = """#!{python}
import json, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
sys.stdin.read()
print(json.dumps({{"type": "system", "subtype": "init", "session_id": "s"}}), flush=True)
print(json.dumps({{"type": "user", "message": {{"content": [{{"type": "tool_result", "content": "x" * {chars}}}]}}}}), flush=True)
time.sleep(60)
"""


def _render_sync_template(tmp_path: Path) -> Path:
    template = TemplateType.SYNC_CLAUDE_CODE
    answers = {
        "template_type": template,
        "project_path": str(tmp_path),
        "agent_name": "cc-bot",
        "agent_directory_name": "cc-bot",
        "description": "test",
        "use_uv": True,
    }
    context = get_project_context(answers, tmp_path, Path("../../"))
    context["template_type"] = template.value
    context["use_uv"] = True
    create_project_structure(tmp_path, context, template, True)
    return tmp_path / "cc_bot" / "project" / "acp.py"


@pytest.fixture
def scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(FAKE_CLAUDE.format(python=sys.executable, chars=LONG_LINE_CHARS))
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{Path(sys.executable).parent}")
    monkeypatch.setenv("AGENT_NAME", "cc-bot")
    monkeypatch.setenv("ACP_URL", "http://localhost:8000")
    monkeypatch.setattr(tracing_processor_manager, "add_tracing_processor_config", lambda _config: None)

    spec = importlib.util.spec_from_file_location("cc_bot_acp", _render_sync_template(tmp_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "TERMINATE_TIMEOUT_SECONDS", FAST_TERMINATE_SECONDS, raising=False)
    return module


async def test_long_stream_json_line_is_read_whole_and_shutdown_is_bounded(scaffold: types.ModuleType) -> None:
    """A tool_result past asyncio's 64 KiB default arrives intact, and a CLI that
    ignores SIGTERM is killed after the grace period instead of hanging cleanup."""
    lines = scaffold._spawn_claude("hi")
    first = await lines.__anext__()
    second = await lines.__anext__()

    started = time.monotonic()
    await asyncio.wait_for(lines.aclose(), SHUTDOWN_BUDGET_SECONDS)
    elapsed = time.monotonic() - started

    assert '"init"' in first
    assert second.count("x") == LONG_LINE_CHARS
    assert elapsed >= FAST_TERMINATE_SECONDS
