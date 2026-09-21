"""Registration metadata: what an agent reports about itself at startup."""

from __future__ import annotations

import pytest

from agentex.lib.utils.registration import build_registration_metadata
from agentex.lib.environment_variables import EnvironmentVariables

SHA = "b362b171a9c4e1f09d8e7a6b5c4d3e2f1a0b9c8d"


def _env(**overrides) -> EnvironmentVariables:
    return EnvironmentVariables(AGENT_NAME="sample-agent", ACP_URL="http://agent", **overrides)


def test_nothing_known_yields_empty_metadata():
    assert build_registration_metadata(_env()) == {}


def test_commit_and_repo_reported_when_set():
    env = _env(AGENT_COMMIT_SHA=SHA, AGENT_SOURCE_REPO="git@github.com:scaleapi/Demo.git")
    assert build_registration_metadata(env) == {
        "commit_sha": SHA,
        "source_repo": "github.com/scaleapi/Demo",
    }


@pytest.mark.parametrize("value", ["latest", "v1.2.3", "rocket_mock_agent-" + SHA, "abc", "   "])
def test_non_commit_values_are_omitted_not_forwarded(value):
    """A field named for a commit never holds an image tag, same rule as __commit_sha__."""
    assert "commit_sha" not in build_registration_metadata(_env(AGENT_COMMIT_SHA=value))


def test_repo_normalization_strips_scheme_and_credentials():
    env = _env(AGENT_SOURCE_REPO="https://x-token:secret@GitHub.com/scaleapi/Demo.git")
    assert build_registration_metadata(env)["source_repo"] == "github.com/scaleapi/Demo"


def test_deployment_id_and_agent_card_still_reported():
    class Card:
        def model_dump(self):
            return {"name": "sample"}

    env = _env(AGENTEX_DEPLOYMENT_ID="dep-1")
    assert build_registration_metadata(env, Card()) == {
        "deployment_id": "dep-1",
        "agent_card": {"name": "sample"},
    }
