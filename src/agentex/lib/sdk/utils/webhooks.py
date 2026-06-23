"""Drive an agent turn from an inbound webhook, inside a forward-route handler.

The Agentex server already exposes a webhook ingress: a request to
``/agents/forward/name/{agent}/{path}`` is signature-verified (GitHub ``sha256=`` /
Slack ``v0:`` HMAC via the agent's registered keys) and proxied to the agent's own
HTTP route. This helper is what that route handler calls to turn the inbound payload
into an agent turn — without each agent re-implementing payload shaping, config
resolution, session continuity, and reply handling.

Typical use inside an agent::

    from fastapi import Request
    from agentex.lib.sdk.utils.webhooks import handle_webhook


    @acp.post("/github-pr")
    async def github_pr(request: Request):
        body = await request.json()
        result = await handle_webhook(
            agent_name="my-agent",
            payload=body,
            acp_type="sync",
            shaper="github_pr",
            params_source="https://<host>/public/v5/agent_configs/<id>/resolve",
            params_source_headers={"x-api-key": ..., "x-selected-account-id": ...},
            wait=True,
        )
        return {"task_id": result.task_id, "reply": result.reply}

Config-by-id: pass ``params_source`` pointing at the platform's config-resolve
endpoint; the resolved params (e.g. system_prompt / harness / model / tools) are
forwarded opaquely to ``task/create``. Or pass inline ``params`` for a one-off.
"""

from __future__ import annotations

import json
import hashlib
from typing import Any, Literal
from dataclasses import field, dataclass
from collections.abc import Mapping, Callable, Awaitable

from agentex.lib import adk
from agentex.lib.utils.logging import make_logger
from agentex.types.task_message_content import TextContent

logger = make_logger(__name__)

# Injectable params fetcher (url -> JSON). Default uses httpx; tests inject a fake.
ParamsFetcher = Callable[[str], Awaitable[dict[str, Any]]]

MAX_BODY_CHARS = 4000
MAX_DIFF_CHARS = 30000


class WebhookError(RuntimeError):
    """Raised when a webhook turn cannot be driven (e.g. params resolution failed)."""


@dataclass
class WebhookResult:
    task_id: str
    # Sync agents reply inline. For async agents, ``reply`` is None unless ``wait`` was
    # set, in which case it is the polled reply (or None if it didn't settle in time).
    reply: str | None = None
    task_metadata: dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- shaping


def session_key(agent_name: str, channel: str, peer_id: str) -> str:
    """Stable per-conversation task name → reused for get-or-create on task/create, so
    repeat events from the same source fold into one task instead of spawning new ones."""
    basis = peer_id or "main"
    digest = hashlib.sha1(f"{agent_name}:{channel}:{basis}".encode()).hexdigest()[:16]
    return f"wh-{channel}-{digest}"


# Top-level fields a generic webhook payload might carry its prompt in, in priority
# order. Matched case-insensitively against the payload's keys.
GENERIC_PROMPT_KEYS = (
    "text",
    "message",
    "prompt",
    "goal",
    "content",
    "body",
    "description",
    "title",
)


def render_generic(body: dict[str, Any]) -> str:
    """Generic payload → prompt text: first non-empty string among GENERIC_PROMPT_KEYS
    (case-insensitive), else raw JSON."""
    lowered = {key.lower(): value for key, value in body.items() if isinstance(key, str)}
    for key in GENERIC_PROMPT_KEYS:
        value = lowered.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(body, indent=2)[:8000]


def shape_github_pr(body: dict[str, Any]) -> tuple[str, str | None, str]:
    """Shape a GitHub/Gitea pull-request webhook into (prompt, peer_id, sender).

    ``peer_id`` is ``repo#number`` so repeated events for the same PR (opened,
    synchronize, ...) fold into one task. Falls back to generic rendering for non-PR
    payloads (ping, issue, ...).
    """
    pull_request = body.get("pull_request")
    if not isinstance(pull_request, dict):
        return render_generic(body), None, _github_actor(body)

    repo = _repo_full_name(body)
    number = pull_request.get("number")
    title = (pull_request.get("title") or "").strip()
    action = (body.get("action") or "").strip()
    description = (pull_request.get("body") or "").strip()
    html_url = pull_request.get("html_url") or pull_request.get("url")

    header = "Pull request"
    if repo and number is not None:
        header = f"Pull request {repo}#{number}"
    elif number is not None:
        header = f"Pull request #{number}"

    lines = [f"{header}: {title}" if title else header]
    if action:
        lines.append(f"Action: {action}")
    if html_url:
        lines.append(f"URL: {html_url}")
    if description:
        lines.extend(["", "Description:", description[:MAX_BODY_CHARS]])

    diff = _inline_diff(body, pull_request)
    if diff:
        lines.extend(["", "Diff:", diff[:MAX_DIFF_CHARS]])
    else:
        # Standard GitHub/Gitea payloads carry a diff/patch URL, not the patch body.
        # Surface it so a tool-enabled agent (or the caller) can fetch the diff; inline
        # `diff` wins. Gitea sends patch_url alongside diff_url, so accept either.
        diff_url = pull_request.get("diff_url") or pull_request.get("patch_url")
        if diff_url:
            lines.extend(["", f"Diff URL: {diff_url}"])

    peer_id = None
    if repo and number is not None:
        peer_id = f"{repo}#{number}"
    elif number is not None:
        peer_id = f"pr#{number}"
    return "\n".join(lines), peer_id, _github_actor(body)


def _repo_full_name(body: dict[str, Any]) -> str | None:
    repo = body.get("repository")
    if isinstance(repo, dict) and isinstance(repo.get("full_name"), str):
        return repo["full_name"] or None
    return None


def _github_actor(body: dict[str, Any]) -> str:
    sender = body.get("sender")
    if isinstance(sender, dict) and isinstance(sender.get("login"), str) and sender["login"]:
        return sender["login"]
    return "webhook"


def _inline_diff(body: dict[str, Any], pull_request: dict[str, Any]) -> str | None:
    for source in (body, pull_request):
        diff = source.get("diff")
        if isinstance(diff, str) and diff.strip():
            return diff.strip()
    return None


# ------------------------------------------------------------------- params resolution


async def _default_fetch(url: str, headers: dict[str, str]) -> dict[str, Any]:
    """GET a params source over HTTP. Imported lazily so callers that only pass inline
    params carry no httpx dependency."""
    import httpx

    request_headers = {"accept": "application/json", **headers}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=request_headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise WebhookError(f"params source request failed: {exc}") from exc
    except ValueError as exc:  # json.JSONDecodeError subclasses ValueError
        raise WebhookError(f"params source returned invalid JSON: {exc}") from exc


async def resolve_remote_params(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    fetch: ParamsFetcher | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Fetch params (+ optional task_metadata) from a config-resolve URL.

    Response shape (lenient)::

        {"params": {...}, "task_metadata": {...}}

    A bare object with no ``params`` key is treated as the params dict itself (minus a
    top-level ``task_metadata``, which is returned separately for stamping).
    """
    do_fetch = fetch or (lambda u: _default_fetch(u, headers or {}))
    payload = await do_fetch(url)
    if not isinstance(payload, dict):
        raise WebhookError("params source returned a non-object response")

    metadata_raw = payload.get("task_metadata")
    task_metadata = {str(k): str(v) for k, v in metadata_raw.items()} if isinstance(metadata_raw, dict) else {}
    params = payload.get("params")
    if not isinstance(params, dict):
        params = {k: v for k, v in payload.items() if k != "task_metadata"}
    return params, task_metadata


# ------------------------------------------------------------------------- dispatch


def _agent_reply_text(messages: object) -> str | None:
    """Join agent-authored text from a message list (sync result or polled stream)."""
    if not isinstance(messages, list):
        return None
    parts = []
    for message in messages:
        content = getattr(message, "content", None)
        if (
            content is not None
            and getattr(content, "author", None) == "agent"
            and getattr(content, "type", None) == "text"
        ):
            text = (getattr(content, "content", "") or "").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts) if parts else None


async def handle_webhook(
    *,
    agent_name: str,
    payload: dict[str, Any],
    acp_type: Literal["sync", "async"] = "sync",
    shaper: Literal["generic", "github_pr"] = "generic",
    channel: str | None = None,
    params: dict[str, Any] | None = None,
    params_source: str | None = None,
    params_source_headers: dict[str, str] | None = None,
    peer_id: str | None = None,
    extra_task_metadata: dict[str, str] | None = None,
    wait: bool = False,
    fetch: ParamsFetcher | None = None,
) -> WebhookResult:
    """Drive an agent turn from a webhook payload, agent-side, via the ADK client.

    - Shapes the payload (generic or GitHub PR) into a prompt + conversation scope.
    - Resolves task params: inline ``params``, or fetched from ``params_source``
      (config-by-id). The platform never interprets params — they're forwarded to the
      agent as ``task/create`` params.
    - Get-or-creates a task keyed on a stable session key, so repeat events fold in.
    - Sends the turn (sync → message/send returns the reply inline; async → event/send,
      with optional ``wait`` to poll for the reply).
    """
    channel = channel or shaper
    if shaper == "github_pr":
        text, derived_peer, sender = shape_github_pr(payload)
        peer_id = peer_id or derived_peer
    else:
        text, sender = render_generic(payload), "webhook"

    task_metadata: dict[str, str] = {"channel": channel, "sender_id": sender}
    if peer_id:
        task_metadata["peer_id"] = peer_id

    resolved_params = dict(params) if params else {}
    if params_source:
        resolved_params, source_metadata = await resolve_remote_params(
            params_source, params_source_headers, fetch=fetch
        )
        # Source metadata + caller extras never override the canonical fields above.
        for key, value in {**source_metadata, **(extra_task_metadata or {})}.items():
            task_metadata.setdefault(key, str(value))
    elif extra_task_metadata:
        for key, value in extra_task_metadata.items():
            task_metadata.setdefault(key, str(value))

    name = session_key(agent_name, channel, peer_id or "")
    # task/create carries only name/params (CreateTaskParams has no task_metadata field),
    # so we create first, then stamp task_metadata via a follow-up update below.
    task = await adk.acp.create_task(
        name=name,
        agent_name=agent_name,
        params=resolved_params or None,
    )

    # Best-effort: stamp the resolved task_metadata (channel/sender/peer_id, plus the
    # display_name etc. from params_source) onto the task so it's labeled in the UI.
    # Failure must never break the run — the metadata is also returned on the result.
    if task_metadata:
        try:
            merged_task_metadata = {
                **_task_metadata_dict(getattr(task, "task_metadata", None)),
                **task_metadata,
            }
            await adk.tasks.update(task_id=task.id, task_metadata=merged_task_metadata)
        except Exception:
            logger.warning("Failed to stamp task_metadata on task %s", task.id, exc_info=True)

    content = TextContent(author="user", content=text, format="markdown")

    if acp_type == "sync":
        messages = await adk.acp.send_message(task_id=task.id, agent_name=agent_name, content=content)
        return WebhookResult(task_id=task.id, reply=_agent_reply_text(messages), task_metadata=task_metadata)

    # Async: when we'll wait for the reply, snapshot existing message ids BEFORE the
    # event so a reused task's prior reply (session continuity) isn't mistaken for it.
    if wait:
        seen_ids, seen_count = await _message_snapshot(task.id)
        await adk.acp.send_event(task_id=task.id, agent_name=agent_name, content=content)
        reply = await _await_reply(task.id, seen_ids, seen_count=seen_count)
    else:
        await adk.acp.send_event(task_id=task.id, agent_name=agent_name, content=content)
        reply = None
    return WebhookResult(task_id=task.id, reply=reply, task_metadata=task_metadata)


def _task_metadata_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


async def _message_snapshot(task_id: str) -> tuple[set[str], int]:
    messages = await adk.messages.list(task_id=task_id)
    messages = messages or []
    return {mid for m in messages if (mid := getattr(m, "id", None)) is not None}, len(messages)


async def _message_ids(task_id: str) -> set[str]:
    # Only track real ids. Keeping None in the set would let a later id-less message
    # collide with it and be wrongly treated as already-seen (dropping a fresh reply).
    seen_ids, _ = await _message_snapshot(task_id)
    return seen_ids


async def _await_reply(
    task_id: str,
    seen_ids: set[str | None],
    *,
    seen_count: int | None = None,
    timeout_s: float = 120.0,
    interval_s: float = 2.0,
    quiescence_s: float = 6.0,
) -> str | None:
    """Poll for THIS turn's reply — agent text in messages that weren't present before
    the event — until it settles (unchanged for ``quiescence_s``) or times out. Filtering
    on new message ids avoids returning a stale prior reply on a reused task."""
    import asyncio

    waited = 0.0
    last: str | None = None
    stable_for = 0.0
    while waited < timeout_s:
        await asyncio.sleep(interval_s)
        waited += interval_s
        messages = await adk.messages.list(task_id=task_id)
        new = []
        for index, message in enumerate(messages or []):
            mid = getattr(message, "id", None)
            if mid is not None and mid not in seen_ids:
                new.append(message)
            elif mid is None and seen_count is not None and index >= seen_count:
                new.append(message)
        text = _agent_reply_text(new)
        if text and text == last:
            stable_for += interval_s
            if stable_for >= quiescence_s:
                return text
        elif text:
            last, stable_for = text, 0.0
    return last
