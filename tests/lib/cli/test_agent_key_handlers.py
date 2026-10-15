"""Tests for deploy-time agent key delivery in `agentex agents deploy --agent-key`."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from kubernetes.client.rest import ApiException

from agentex import ConflictError
from agentex.lib.cli.handlers import deploy_handlers, agent_key_handlers
from agentex.config.agent_config import AgentConfig
from agentex.config.build_config import BuildConfig, BuildContext
from agentex.config.agent_manifest import AgentManifest
from agentex.config.deployment_config import ImageConfig, DeploymentConfig
from agentex.lib.cli.utils.exceptions import DeploymentError
from agentex.lib.cli.handlers.deploy_handlers import InputDeployOverrides
from agentex.lib.cli.handlers.agent_key_handlers import (
    AGENT_ID_ANNOTATION,
    bootstrap_agent_api_key,
    agent_api_key_secret_name,
    inject_agent_api_key_secret_ref,
)

AGENT_ID = "agent-123"
ISSUED_KEY = "issued-key-value"
SECRET_NAME = agent_api_key_secret_name(AGENT_ID)


def _manifest() -> AgentManifest:
    return AgentManifest(
        build=BuildConfig(context=BuildContext(root=".", dockerfile="Dockerfile", dockerignore=None)),
        agent=AgentConfig(name="emu-tax", description="Files emu taxes", acp_type="async"),
        deployment=DeploymentConfig(image=ImageConfig(repository="registry.example.com/emu-tax", tag="v1")),
    )


def _api_exception(status: int) -> ApiException:
    return ApiException(status=status)


def _conflict() -> ConflictError:
    request = httpx.Request("POST", "http://agentex/agents/agent-123/internal-key")
    return ConflictError("exists", response=httpx.Response(409, request=request), body=None)


def _stored_secret(agent_id: str = AGENT_ID) -> SimpleNamespace:
    return SimpleNamespace(
        metadata=SimpleNamespace(annotations={AGENT_ID_ANNOTATION: agent_id}),
        data={"AGENT_API_KEY": base64.b64encode(b"stored").decode()},
    )


@pytest.fixture
def agentex_client() -> MagicMock:
    agentex = MagicMock()
    agentex.agents.register_build.return_value = SimpleNamespace(id=AGENT_ID)
    agentex.post.return_value = {"agent_id": AGENT_ID, "agent_api_key_id": "k-1", "agent_api_key": ISSUED_KEY}
    return agentex


@pytest.fixture
def k8s(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    v1 = MagicMock()
    v1.read_namespaced_secret.side_effect = _api_exception(404)
    monkeypatch.setattr(agent_key_handlers, "get_k8s_client", lambda _context=None: v1)
    return v1


def _bootstrap(agentex_client: MagicMock, *, replace: bool = False) -> str:
    return bootstrap_agent_api_key(
        agentex_client=agentex_client,
        manifest=_manifest(),
        namespace="agents",
        context="dev-cluster",
        replace_existing_key=replace,
    )


def _created_values(k8s: MagicMock) -> list[str]:
    return [c.kwargs["body"].string_data["AGENT_API_KEY"] for c in k8s.create_namespaced_secret.call_args_list]


class TestBootstrap:
    def test_first_deploy_preflights_then_issues_then_stores(self, agentex_client, k8s):
        assert _bootstrap(agentex_client) == SECRET_NAME

        agentex_client.agents.register_build.assert_called_once_with(name="emu-tax", description="Files emu taxes")
        agentex_client.post.assert_called_once_with(f"/agents/{AGENT_ID}/internal-key", body={}, cast_to=object)
        preflight, store = k8s.create_namespaced_secret.call_args_list
        assert preflight.kwargs["dry_run"] == "All"
        assert preflight.kwargs["body"].string_data["AGENT_API_KEY"] != ISSUED_KEY
        assert "dry_run" not in store.kwargs
        assert store.kwargs["body"].metadata.annotations == {AGENT_ID_ANNOTATION: AGENT_ID}
        assert _created_values(k8s)[1] == ISSUED_KEY

    def test_redeploy_reuses_stored_secret_without_issuing(self, agentex_client, k8s):
        k8s.read_namespaced_secret.side_effect = None
        k8s.read_namespaced_secret.return_value = _stored_secret()

        assert _bootstrap(agentex_client) == SECRET_NAME

        agentex_client.post.assert_not_called()
        k8s.create_namespaced_secret.assert_not_called()

    def test_refuses_secret_that_belongs_to_another_agent(self, agentex_client, k8s):
        k8s.read_namespaced_secret.side_effect = None
        k8s.read_namespaced_secret.return_value = _stored_secret("other-agent")

        with pytest.raises(DeploymentError, match="not the managed key"):
            _bootstrap(agentex_client)

        agentex_client.post.assert_not_called()

    def test_existing_unreadable_key_fails_closed_without_replacing(self, agentex_client, k8s):
        agentex_client.post.side_effect = _conflict()

        with pytest.raises(DeploymentError, match="--replace-agent-key"):
            _bootstrap(agentex_client)

        assert agentex_client.post.call_args.kwargs["body"] == {}
        assert [c.kwargs.get("dry_run") for c in k8s.create_namespaced_secret.call_args_list] == ["All"]

    def test_migration_replaces_and_stores(self, agentex_client, k8s):
        assert _bootstrap(agentex_client, replace=True) == SECRET_NAME

        assert agentex_client.post.call_args.kwargs["body"] == {"replace": True}
        assert _created_values(k8s)[1] == ISSUED_KEY

    def test_migration_refused_once_a_key_is_stored(self, agentex_client, k8s):
        k8s.read_namespaced_secret.side_effect = None
        k8s.read_namespaced_secret.return_value = _stored_secret()

        with pytest.raises(DeploymentError, match="already exists"):
            _bootstrap(agentex_client, replace=True)

        agentex_client.post.assert_not_called()

    def test_preflight_rejection_issues_no_key(self, agentex_client, k8s):
        k8s.create_namespaced_secret.side_effect = _api_exception(403)

        with pytest.raises(DeploymentError, match="no agent key was issued"):
            _bootstrap(agentex_client)

        agentex_client.post.assert_not_called()

    def test_store_failure_after_issuance_does_not_leak_the_key(self, agentex_client, k8s):
        k8s.create_namespaced_secret.side_effect = [None, _api_exception(500)]

        with pytest.raises(DeploymentError) as excinfo:
            _bootstrap(agentex_client, replace=True)

        assert ISSUED_KEY not in str(excinfo.value)
        assert excinfo.value.__cause__ is None
        assert "without --replace-agent-key" in str(excinfo.value)

    def test_concurrent_store_reuses_the_winner(self, agentex_client, k8s):
        k8s.create_namespaced_secret.side_effect = [None, _api_exception(409)]
        k8s.read_namespaced_secret.side_effect = [_api_exception(404), _stored_secret()]

        assert _bootstrap(agentex_client) == SECRET_NAME

    def test_provisioning_error_is_not_chained(self, agentex_client, k8s):
        agentex_client.post.side_effect = RuntimeError(f"bad body containing {ISSUED_KEY}")

        with pytest.raises(DeploymentError) as excinfo:
            _bootstrap(agentex_client)

        assert ISSUED_KEY not in str(excinfo.value)
        assert excinfo.value.__cause__ is None

    def test_rejects_key_issued_for_another_agent(self, agentex_client, k8s):
        agentex_client.post.return_value = {"agent_id": "other", "agent_api_key": ISSUED_KEY}

        with pytest.raises(DeploymentError, match="different agent"):
            _bootstrap(agentex_client)

        assert len(k8s.create_namespaced_secret.call_args_list) == 1


class TestInjection:
    def test_adds_secret_ref_to_agent_and_worker(self):
        values: dict[str, Any] = {"env": [{"name": "A", "value": "1"}], "temporal-worker": {"enabled": True}}

        inject_agent_api_key_secret_ref(values, SECRET_NAME)

        expected = {"name": "AGENT_API_KEY", "secretName": SECRET_NAME, "secretKey": "AGENT_API_KEY"}
        assert values["secretEnvVars"] == [expected]
        assert values["temporal-worker"]["secretEnvVars"] == [expected]

    @pytest.mark.parametrize(
        "values",
        [
            {"env": [{"name": "AGENT_API_KEY", "value": "x"}]},
            {"secretEnvVars": [{"name": "AGENT_API_KEY", "secretName": "mine", "secretKey": "k"}]},
            {"temporal-worker": {"env": [{"name": "AGENT_API_KEY", "value": "x"}]}},
            {"secretEnvVars": [{"name": "OTHER", "secretName": SECRET_NAME, "secretKey": "AGENT_API_KEY"}]},
        ],
    )
    def test_rejects_caller_supplied_key_or_managed_secret(self, values):
        with pytest.raises(DeploymentError):
            inject_agent_api_key_secret_ref(values, SECRET_NAME)


class TestDeployAgent:
    @pytest.fixture
    def helm(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> MagicMock:
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("")
        run = MagicMock()
        monkeypatch.setattr(deploy_handlers.subprocess, "run", run)
        monkeypatch.setattr(deploy_handlers, "check_helm_installed", lambda: True)
        monkeypatch.setattr(deploy_handlers, "check_and_switch_cluster_context", lambda _c: None)
        monkeypatch.setattr(deploy_handlers, "load_agent_manifest", lambda file_path: _manifest())  # noqa: ARG005
        monkeypatch.setattr(deploy_handlers, "add_helm_repo", lambda *_a: None)
        monkeypatch.setattr(deploy_handlers, "resolve_chart", lambda **_k: ("scale-egp/agentex-agent", "0.6.0"))
        monkeypatch.setattr(deploy_handlers, "add_acp_command_to_helm_values", lambda *_a: None)
        monkeypatch.setattr(deploy_handlers, "Agentex", MagicMock)
        monkeypatch.setenv("AGENTEX_BASE_URL", "http://agentex.dev.example")
        run.manifest_path = str(manifest_path)
        return run

    def _deploy(self, helm: MagicMock, **kwargs: Any) -> None:
        deploy_handlers.deploy_agent(
            manifest_path=helm.manifest_path,
            cluster_name="dev-cluster",
            namespace="agents",
            deploy_overrides=InputDeployOverrides(),
            **kwargs,
        )

    def test_key_delivery_failure_never_reaches_helm(self, helm, monkeypatch):
        def fail(**_kwargs):
            raise DeploymentError("Agentex unavailable")

        monkeypatch.setattr(deploy_handlers, "bootstrap_agent_api_key", fail)

        with pytest.raises(DeploymentError, match="Agentex unavailable"):
            self._deploy(helm, agent_key=True)

        helm.assert_not_called()

    def test_values_file_carries_only_the_secret_reference(self, helm, monkeypatch):
        captured: dict[str, Any] = {}
        create_values_file = deploy_handlers.create_helm_values_file

        def capture(values):
            captured.update(values)
            return create_values_file(values)

        monkeypatch.setattr(deploy_handlers, "bootstrap_agent_api_key", lambda **_k: SECRET_NAME)
        monkeypatch.setattr(deploy_handlers, "create_helm_values_file", capture)

        self._deploy(helm, agent_key=True)

        assert {"name": "AGENT_API_KEY", "secretName": SECRET_NAME, "secretKey": "AGENT_API_KEY"} in captured[
            "secretEnvVars"
        ]
        assert helm.call_count == 2  # helm status, then upgrade

    def test_without_flag_no_key_is_requested(self, helm, monkeypatch):
        bootstrap = MagicMock()
        monkeypatch.setattr(deploy_handlers, "bootstrap_agent_api_key", bootstrap)

        self._deploy(helm)

        bootstrap.assert_not_called()

    def test_replace_requires_agent_key(self, helm):
        with pytest.raises(DeploymentError, match="requires --agent-key"):
            self._deploy(helm, replace_agent_key=True)

        helm.assert_not_called()

    def test_agent_key_requires_explicit_agentex_url(self, helm, monkeypatch):
        monkeypatch.delenv("AGENTEX_BASE_URL")
        bootstrap = MagicMock()
        monkeypatch.setattr(deploy_handlers, "bootstrap_agent_api_key", bootstrap)

        with pytest.raises(DeploymentError, match="AGENTEX_BASE_URL"):
            self._deploy(helm, agent_key=True)

        bootstrap.assert_not_called()
        helm.assert_not_called()
