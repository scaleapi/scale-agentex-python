"""Commit-SHA stamping.

The contract that matters: with ``AGENT_COMMIT_SHA`` absent and no ``enable()``
call, nothing is stamped, so upgrading the SDK never starts emitting this field
on its own. A deployment that sets the env var turns it on without agent code.
"""

from __future__ import annotations

import pytest

from agentex.lib.core.tracing import code_revision

SHA = "b362b171a9c4e1f09d8e7a6b5c4d3e2f1a0b9c8d"


@pytest.fixture(autouse=True)
def _reset():
    """State is process-wide (like the lineage registry), so isolate each test."""
    code_revision.disable()
    yield
    code_revision.disable()


class TestEnablement:
    def test_off_when_env_absent(self, monkeypatch):
        """The import-time hook ignores AGENT_VERSION; that fallback needs enable()."""
        monkeypatch.delenv("AGENT_COMMIT_SHA", raising=False)
        monkeypatch.setenv("AGENT_VERSION", SHA)
        code_revision._enable_from_environment()
        assert code_revision.commit_sha() is None
        assert code_revision.is_enabled() is False

    def test_env_set_at_startup_enables_without_a_call(self, monkeypatch):
        """The cloud deploy sets AGENT_COMMIT_SHA from the build record; the agent
        should not need to know."""
        monkeypatch.setenv("AGENT_COMMIT_SHA", SHA)
        code_revision._enable_from_environment()
        assert code_revision.commit_sha() == SHA

    def test_env_set_after_import_needs_enable(self, monkeypatch):
        monkeypatch.setenv("AGENT_COMMIT_SHA", SHA)
        assert code_revision.commit_sha() is None
        code_revision.enable()
        assert code_revision.commit_sha() == SHA

    def test_bad_env_at_startup_leaves_it_off(self, monkeypatch):
        monkeypatch.setenv("AGENT_COMMIT_SHA", "latest")
        code_revision._enable_from_environment()
        assert code_revision.commit_sha() is None

    def test_enable_reads_agent_commit_sha(self, monkeypatch):
        monkeypatch.setenv("AGENT_COMMIT_SHA", SHA)
        code_revision.enable()
        assert code_revision.commit_sha() == SHA
        assert code_revision.is_enabled() is True

    def test_explicit_argument_wins(self, monkeypatch):
        monkeypatch.setenv("AGENT_COMMIT_SHA", SHA)
        code_revision.enable("7f3a91c2")
        assert code_revision.commit_sha() == "7f3a91c2"

    def test_disable_turns_it_back_off(self, monkeypatch):
        monkeypatch.setenv("AGENT_COMMIT_SHA", SHA)
        code_revision.enable()
        code_revision.disable()
        assert code_revision.commit_sha() is None


class TestValueIsAlwaysACommit:
    """A field named for a commit must never hold an image tag."""

    @pytest.mark.parametrize(
        "value",
        [
            "latest",
            "v1.2.3",
            "0.2.4-v4",
            "rocket_mock_agent-b362b171a9c4e1f09d8e7a6b5c4d3e2f1a0b9c8d",  # AWS ECR composite
            "abc",  # shorter than git's 7-char minimum
            "z" * 40,  # right length, not hex
        ],
    )
    def test_non_sha_is_refused(self, monkeypatch, value):
        monkeypatch.setenv("AGENT_COMMIT_SHA", value)
        code_revision.enable()
        assert code_revision.commit_sha() is None

    @pytest.mark.parametrize("value", [SHA, SHA.upper(), "b362b17", "a" * 64])
    def test_git_object_names_are_accepted(self, monkeypatch, value):
        monkeypatch.setenv("AGENT_COMMIT_SHA", value)
        code_revision.enable()
        assert code_revision.commit_sha() == value

    def test_whitespace_only_is_refused(self, monkeypatch):
        monkeypatch.setenv("AGENT_COMMIT_SHA", "   ")
        code_revision.enable()
        assert code_revision.commit_sha() is None

    def test_enable_with_nothing_available_is_a_no_op(self, monkeypatch):
        monkeypatch.delenv("AGENT_COMMIT_SHA", raising=False)
        monkeypatch.delenv("AGENT_VERSION", raising=False)
        code_revision.enable()
        assert code_revision.commit_sha() is None


class TestAgentVersionFallback:
    def test_falls_back_to_agent_version_when_sha_shaped(self, monkeypatch):
        """A platform deploy already sets AGENT_VERSION; on GCP/Azure it is a
        bare SHA, so an opting-in agent needs no extra plumbing."""
        monkeypatch.delenv("AGENT_COMMIT_SHA", raising=False)
        monkeypatch.setenv("AGENT_VERSION", SHA)
        code_revision.enable()
        assert code_revision.commit_sha() == SHA

    def test_does_not_fall_back_to_a_non_sha_agent_version(self, monkeypatch):
        """AGENT_VERSION is 'latest' or an AWS composite much of the time."""
        monkeypatch.delenv("AGENT_COMMIT_SHA", raising=False)
        monkeypatch.setenv("AGENT_VERSION", "latest")
        code_revision.enable()
        assert code_revision.commit_sha() is None

    def test_bad_explicit_value_does_not_fall_through(self, monkeypatch):
        """An explicit AGENT_COMMIT_SHA is a statement of intent: if it is wrong,
        say so rather than silently substituting the image tag."""
        monkeypatch.setenv("AGENT_COMMIT_SHA", "not-a-sha")
        monkeypatch.setenv("AGENT_VERSION", SHA)
        code_revision.enable()
        assert code_revision.commit_sha() is None
