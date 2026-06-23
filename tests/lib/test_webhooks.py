"""Unit tests for the SDK webhook helper (agentex.lib.sdk.utils.webhooks)."""

from __future__ import annotations

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
        )

        stamped_metadata = self.stamped["task_metadata"]
        assert stamped_metadata["labels"] == ["customer-facing"]
        assert stamped_metadata["agent_config_id"] == "cfg-9"
        assert stamped_metadata["channel"] == "github_pr"

    async def test_async_without_wait_sends_event_and_returns_no_reply(self):
        result = await handle_webhook(agent_name="a", payload={"text": "go"}, acp_type="async", wait=False)
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
