"""Tests for the environment `agentex agents run` hands to the ACP and worker processes."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentex.lib.cli.commands.init import (
    TemplateType,
    get_project_context,
    create_project_structure,
)
from agentex.lib.cli.handlers.run_handlers import create_agent_environment
from agentex.lib.sdk.config.agent_manifest import load_agent_manifest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A scaffolded Sync ACP project, so the manifest is a real one."""
    answers = {
        "template_type": TemplateType.SYNC,
        "project_path": str(tmp_path),
        "agent_name": "env-agent",
        "agent_directory_name": "env-agent",
        "description": "An Agentex agent",
        "use_uv": True,
    }
    context = get_project_context(answers, tmp_path, Path("../../"))
    context["template_type"] = TemplateType.SYNC.value
    context["use_uv"] = True
    create_project_structure(tmp_path, context, TemplateType.SYNC, use_uv=True)
    return tmp_path / context["project_name"]


def test_dotenv_next_to_manifest_is_loaded(project_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Values in <manifest dir>/.env reach the subprocess environment."""
    (project_dir / ".env").write_text("FROM_DOTENV=1\nLITELLM_API_KEY=sk-test\n")
    monkeypatch.delenv("FROM_DOTENV", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    manifest = load_agent_manifest(file_path=str(project_dir / "manifest.yaml"))

    env = create_agent_environment(manifest, manifest_dir=project_dir)

    assert env["FROM_DOTENV"] == "1"
    assert env["LITELLM_API_KEY"] == "sk-test"
    assert env["ENVIRONMENT"] == "development"


def test_shell_variables_win_over_dotenv(project_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """A variable already exported in the shell is not overridden by .env."""
    (project_dir / ".env").write_text("PRESET=from-dotenv\n")
    monkeypatch.setenv("PRESET", "from-shell")
    manifest = load_agent_manifest(file_path=str(project_dir / "manifest.yaml"))

    env = create_agent_environment(manifest, manifest_dir=project_dir)

    assert env["PRESET"] == "from-shell"


def test_missing_dotenv_and_no_manifest_dir_are_fine(project_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """No .env file, or no manifest_dir given, still builds a normal environment."""
    monkeypatch.delenv("FROM_DOTENV", raising=False)
    manifest = load_agent_manifest(file_path=str(project_dir / "manifest.yaml"))

    assert "FROM_DOTENV" not in create_agent_environment(manifest, manifest_dir=project_dir)
    assert "FROM_DOTENV" not in create_agent_environment(manifest)


def test_dotenv_overrides_builtin_local_defaults_but_not_environment(project_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """.env may point local runs at a custom Redis/Temporal; ENVIRONMENT stays development."""
    (project_dir / ".env").write_text("REDIS_URL=redis://custom:6380\nTEMPORAL_ADDRESS=temporal.internal:7233\nENVIRONMENT=production\n")
    for key in ("REDIS_URL", "TEMPORAL_ADDRESS", "ENVIRONMENT"):
        monkeypatch.delenv(key, raising=False)
    manifest = load_agent_manifest(file_path=str(project_dir / "manifest.yaml"))

    env = create_agent_environment(manifest, manifest_dir=project_dir)

    assert env["REDIS_URL"] == "redis://custom:6380"
    assert env["TEMPORAL_ADDRESS"] == "temporal.internal:7233"
    assert env["ENVIRONMENT"] == "development"
