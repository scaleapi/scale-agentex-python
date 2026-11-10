"""Unit tests for the SDK webhook helper (agentex.lib.sdk.utils.webhooks).

The turn-driving tests pass ``trust_caller=True`` because provenance is not what they
are about; ``TestProvenance`` covers the signature gate itself.
"""

from __future__ import annotations

import hmac
import json
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agentex.lib import adk
from agentex.lib.sdk.utils.webhooks import (
    WebhookError,
    session_key,
    handle_webhook,
    render_generic,
    shape_github_pr,
    resolve_remote_params,
)
from agentex.lib.sdk.utils.webhook_signatures import (
    WebhookVerification,
    WebhookSignatureError,
    verify_slack_signature,
    verify_github_signature,
)


def _pr_payload(**pr_overrides) -> dict:
    pr = {
        "number": 42,
        "title": "Add retry to uploader",
        "body": "Adds backoff on 503.",
        "html_url": "https://example.com/acme/widgets/pull/42",
    }
    pr.update(pr_overrides)
    return {
        "action": "opened",
        "repository": {"full_name": "acme/widgets"},
        "sender": {"login": "octocat"},
        "pull_request": pr,
    }


class TestSessionKey:
    def test_stable_and_folds_same_conversation(self):
        a = session_key("agent-1", "github_pr", "acme/widgets#42")
        b = session_key("agent-1", "github_pr", "acme/widgets#42")
        assert a == b and a.startswith("wh-github_pr-")

    def test_differs_by_peer(self):
        assert session_key("a", "github_pr", "r#1") != session_key("a", "github_pr", "r#2")


class TestShaping:
    def test_render_generic_prefers_text_field(self):
        assert render_generic({"text": "hello"}) == "hello"

    def test_render_generic_falls_back_to_json(self):
        assert "zen" in render_generic({"zen": "be awesome"})

    def test_render_generic_matches_keys_case_insensitively(self):
        assert render_generic({"Message": "hi there"}) == "hi there"

    def test_render_generic_supports_broadened_keys(self):
        assert render_generic({"description": "do the thing"}) == "do the thing"

    def test_github_pr_shape(self):
        text, peer, sender = shape_github_pr(_pr_payload())
        assert "Pull request acme/widgets#42: Add retry to uploader" in text
        assert "Action: opened" in text
        assert "Adds backoff on 503." in text
        assert peer == "acme/widgets#42"
        assert sender == "octocat"

    def test_github_pr_includes_diff(self):
        body = _pr_payload()
        body["pull_request"]["diff"] = "diff --git a/x b/x\n+line"
        text, _, _ = shape_github_pr(body)
        assert "Diff:" in text and "+line" in text

    def test_non_pr_payload_falls_back_to_generic(self):
        text, peer, _ = shape_github_pr({"zen": "be awesome", "hook_id": 1})
        assert "Pull request" not in text
        assert "be awesome" in text
        assert peer is None


class TestResolveRemoteParams:
    async def test_envelope_with_params_and_metadata(self):
        async def fetch(_url):
            return {"params": {"system_prompt": "x", "model": "m"}, "task_metadata": {"cfg": "1"}}

        params, md = await resolve_remote_params("https://h/resolve", fetch=fetch)
        assert params == {"system_prompt": "x", "model": "m"}
        assert md == {"cfg": "1"}

    async def test_bare_object_is_params_minus_task_metadata(self):
        async def fetch(_url):
            return {"system_prompt": "x", "task_metadata": {"cfg": "1"}}

        params, md = await resolve_remote_params("https://h/resolve", fetch=fetch)
        assert params == {"system_prompt": "x"}  # task_metadata stripped from params
        assert md == {"cfg": "1"}

    async def test_non_object_raises(self):
        async def fetch(_url):
            return ["nope"]

        with pytest.raises(WebhookError):
            await resolve_remote_params("https://h/resolve", fetch=fetch)


def _agent_msg(text: str):
    return SimpleNamespace(content=SimpleNamespace(author="agent", type="text", content=text))


class TestHandleWebhook:
    @pytest.fixture(autouse=True)
    def _mock_adk(self, monkeypatch):
        self.created = {}
        self.sent = {}
        self.stamped = {}
        self.created_task_metadata = {}

        async def create_task(*, name, agent_name, params=None, request=None, **_):
            self.created = {"name": name, "agent_name": agent_name, "params": params, "request": request}
            return SimpleNamespace(id="task-1", task_metadata=self.created_task_metadata)

        async def send_message(*, task_id, agent_name, content, **_):
            self.sent = {"task_id": task_id, "content": content}
            return [_agent_msg("Looks good — ship it.")]

        async def update_task(*, task_id, task_metadata=None, **_):
            self.stamped = {"task_id": task_id, "task_metadata": task_metadata}
            return SimpleNamespace(id=task_id)

        send_event = AsyncMock()
        monkeypatch.setattr(adk.acp, "create_task", create_task)
        monkeypatch.setattr(adk.acp, "send_message", send_message)
        monkeypatch.setattr(adk.acp, "send_event", send_event)
        monkeypatch.setattr(adk.tasks, "update", update_task)
        self.send_event = send_event
        yield

    async def test_sync_github_pr_with_config_by_id(self):
        async def fake_resolve(_url):
            return {"params": {"system_prompt": "review"}, "task_metadata": {"agent_config_id": "cfg-9"}}

        result = await handle_webhook(
            agent_name="golden-agent",
            payload=_pr_payload(),
            acp_type="sync",
            shaper="github_pr",
            params_source="https://h/v5/agent_configs/cfg-9/resolve",
            fetch=fake_resolve,
            trust_caller=True,
        )

        assert result.reply == "Looks good — ship it."
        assert self.created["params"] == {"system_prompt": "review"}
        # metadata is returned on the result (SDK task/create can't carry it)
        md = result.task_metadata
        assert md["channel"] == "github_pr"
        assert md["peer_id"] == "acme/widgets#42"
        assert md["agent_config_id"] == "cfg-9"
        # task folded on a stable session key
        assert self.created["name"].startswith("wh-github_pr-")
        # metadata is also stamped onto the task (best-effort) so it's labeled in the UI
        assert self.stamped["task_id"] == "task-1"
        assert self.stamped["task_metadata"]["peer_id"] == "acme/widgets#42"
        assert self.stamped["task_metadata"]["agent_config_id"] == "cfg-9"

    async def test_inline_params_no_fetch(self):
        result = await handle_webhook(
            agent_name="a",
            payload={"text": "hi"},
            acp_type="sync",
            params={"system_prompt": "inline"},
            trust_caller=True,
        )
        assert result.reply == "Looks good — ship it."
        assert self.created["params"] == {"system_prompt": "inline"}

    async def test_source_metadata_cannot_override_canonical(self):
        async def fake_resolve(_url):
            return {"params": {}, "task_metadata": {"channel": "spoofed"}}

        result = await handle_webhook(
            agent_name="a",
            payload=_pr_payload(),
            shaper="github_pr",
            params_source="https://h/resolve",
            fetch=fake_resolve,
            trust_caller=True,
        )
        assert result.task_metadata["channel"] == "github_pr"

    async def test_task_metadata_preserves_existing_keys_on_reused_task(self):
        self.created_task_metadata = {
            "labels": ["customer-facing"],
            "agent_config_id": "old-cfg",
            "channel": "old-channel",
        }

        async def fake_resolve(_url):
            return {"params": {}, "task_metadata": {"agent_config_id": "cfg-9"}}

        await handle_webhook(
            agent_name="a",
            payload=_pr_payload(),
            shaper="github_pr",
            params_source="https://h/resolve",
            fetch=fake_resolve,
            trust_caller=True,
        )

        stamped_metadata = self.stamped["task_metadata"]
        assert stamped_metadata["labels"] == ["customer-facing"]
        assert stamped_metadata["agent_config_id"] == "cfg-9"
        assert stamped_metadata["channel"] == "github_pr"

    async def test_async_without_wait_sends_event_and_returns_no_reply(self):
        result = await handle_webhook(
            agent_name="a", payload={"text": "go"}, acp_type="async", wait=False, trust_caller=True
        )
        assert result.reply is None
        self.send_event.assert_awaited_once()


class TestAwaitReplyIgnoresStalePriorReply:
    async def test_returns_only_new_agent_text_on_reused_task(self, monkeypatch):
        from agentex.lib.sdk.utils.webhooks import _await_reply

        old = _agent_msg("OLD reply")
        old.id = "m1"
        new = _agent_msg("NEW reply")
        new.id = "m2"
        calls = {"n": 0}

        async def fake_list(*, task_id, **_):
            calls["n"] += 1
            return [old] if calls["n"] < 2 else [old, new]  # new appears on 2nd poll

        async def no_sleep(_seconds):
            return None

        monkeypatch.setattr(adk.messages, "list", fake_list)
        monkeypatch.setattr("asyncio.sleep", no_sleep)

        # baseline = the pre-existing old message; only m2 (NEW) should be returned
        reply = await _await_reply("task-1", {"m1"}, interval_s=0.0, quiescence_s=0.0)
        assert reply == "NEW reply"

    async def test_returns_idless_agent_text_after_snapshot(self, monkeypatch):
        from agentex.lib.sdk.utils.webhooks import _await_reply

        old = _agent_msg("OLD reply")
        old.id = None
        new = _agent_msg("NEW reply")
        new.id = None
        calls = {"n": 0}

        async def fake_list(*, task_id, **_):
            calls["n"] += 1
            return [old] if calls["n"] < 2 else [old, new]

        async def no_sleep(_seconds):
            return None

        monkeypatch.setattr(adk.messages, "list", fake_list)
        monkeypatch.setattr("asyncio.sleep", no_sleep)

        reply = await _await_reply(
            "task-1",
            set(),
            seen_count=1,
            interval_s=0.0,
            quiescence_s=0.0,
        )
        assert reply == "NEW reply"


class TestProvenance:
    """VULN-3137: the route is reachable directly, so a payload is not evidence."""

    def test_github_signature_round_trips(self):
        body = b'{"zen":"be awesome"}'
        sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
        # Does not raise.
        verify_github_signature("s3cret", body, {"X-Hub-Signature-256": sig})

    @pytest.mark.parametrize(
        ("label", "headers"),
        [
            ("absent", {}),
            ("empty", {"X-Hub-Signature-256": ""}),
            ("wrong-digest", {"X-Hub-Signature-256": "sha256=" + "a" * 64}),
            ("unprefixed", {"X-Hub-Signature-256": "a" * 64}),
        ],
    )
    def test_github_signature_rejected(self, label, headers):
        with pytest.raises(WebhookSignatureError):
            verify_github_signature("s3cret", b"{}", headers)

    def test_github_signature_is_over_the_raw_bytes(self):
        """A re-serialised dict is different bytes and must not verify.

        This is why handle_webhook takes the raw body rather than signing the parsed
        payload: json.dumps(json.loads(x)) != x in general.
        """
        raw = b'{"a": 1,  "b": 2}'
        sig = "sha256=" + hmac.new(b"k", raw, hashlib.sha256).hexdigest()
        reserialised = json.dumps(json.loads(raw)).encode()
        assert reserialised != raw
        verify_github_signature("k", raw, {"X-Hub-Signature-256": sig})
        with pytest.raises(WebhookSignatureError):
            verify_github_signature("k", reserialised, {"X-Hub-Signature-256": sig})

    def test_slack_signature_round_trips_and_checks_freshness(self):
        body = b"token=x&team_id=T1"
        ts = "1700000000"
        basis = b"v0:" + ts.encode() + b":" + body
        sig = "v0=" + hmac.new(b"s3cret", basis, hashlib.sha256).hexdigest()
        headers = {"X-Slack-Signature": sig, "X-Slack-Request-Timestamp": ts}

        verify_slack_signature("s3cret", body, headers, now=1700000030)

        # Same signature, replayed well outside the window.
        with pytest.raises(WebhookSignatureError, match="more than"):
            verify_slack_signature("s3cret", body, headers, now=1700000000 + 3600)
        # ... and a future-dated timestamp is refused too.
        with pytest.raises(WebhookSignatureError, match="more than"):
            verify_slack_signature("s3cret", body, headers, now=1700000000 - 3600)

    def test_an_empty_secret_never_verifies(self):
        body = b"{}"
        sig = "sha256=" + hmac.new(b"", body, hashlib.sha256).hexdigest()
        with pytest.raises(WebhookSignatureError, match="No webhook secret"):
            verify_github_signature("", body, {"X-Hub-Signature-256": sig})

    def test_headers_are_matched_case_insensitively(self):
        body = b"{}"
        sig = "sha256=" + hmac.new(b"k", body, hashlib.sha256).hexdigest()
        verify_github_signature("k", body, {"x-hub-signature-256": sig})
        verify_github_signature("k", body, {"X-HUB-SIGNATURE-256": sig})


class TestHandleWebhookProvenance:
    @pytest.fixture(autouse=True)
    def _never_reached(self, monkeypatch):
        """Any ADK call at all means the gate let an unverified payload through."""
        boom = AsyncMock(side_effect=AssertionError("handle_webhook drove a turn"))
        monkeypatch.setattr(adk.acp, "create_task", boom)
        monkeypatch.setattr(adk.acp, "send_message", boom)
        monkeypatch.setattr(adk.acp, "send_event", boom)
        monkeypatch.setattr(adk.tasks, "update", boom)

    async def test_an_unverified_payload_drives_no_turn(self):
        """The finding's direct POST: a well-formed body and nothing else."""
        with pytest.raises(WebhookSignatureError, match="without provenance"):
            await handle_webhook(agent_name="golden-agent", payload=_pr_payload(), shaper="github_pr")

    async def test_a_forged_signature_drives_no_turn(self):
        raw = json.dumps(_pr_payload()).encode()
        with pytest.raises(WebhookSignatureError, match="Invalid"):
            await handle_webhook(
                agent_name="golden-agent",
                payload=_pr_payload(),
                shaper="github_pr",
                verify=WebhookVerification(
                    source="github",
                    secret="the-real-secret",
                    body=raw,
                    headers={"X-Hub-Signature-256": "sha256=" + "a" * 64},
                ),
            )


class TestSessionBinding:
    """VULN-3137 criterion 2: naming a conversation requires the secret."""

    def test_an_unverified_caller_cannot_compute_a_verified_tasks_name(self):
        # Public data: repo name and PR number.
        peer = "acme/widgets#42"
        guessed = session_key("golden-agent", "github_pr", peer)
        real = session_key("golden-agent", "github_pr", peer, secret="the-real-secret")
        assert guessed != real, "the task name must not be derivable from public data"

    def test_two_installations_watching_one_repo_stay_separate(self):
        peer = "acme/widgets#42"
        a = session_key("golden-agent", "github_pr", peer, secret="secret-a")
        b = session_key("golden-agent", "github_pr", peer, secret="secret-b")
        assert a != b

    def test_the_same_secret_still_folds_repeat_events(self):
        peer = "acme/widgets#42"
        first = session_key("golden-agent", "github_pr", peer, secret="s")
        second = session_key("golden-agent", "github_pr", peer, secret="s")
        assert first == second and first.startswith("wh-github_pr-")
