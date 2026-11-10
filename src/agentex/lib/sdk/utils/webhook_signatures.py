"""Prove an inbound webhook really came from GitHub or Slack, agent-side.

The Agentex control plane verifies a webhook's HMAC at its
``/agents/forward/name/{agent}/{path}`` ingress and then proxies the request to the
agent's own HTTP route. That verification does NOT travel with the request: the
agent's route is an ordinary FastAPI route on an app bound to ``0.0.0.0:8000``, so
any peer that can reach the pod port can POST the same shape of body directly, and
nothing about the request distinguishes it from a proxied one (VULN-3137). FastACP
adds no authentication to agent-defined routes either -- its ``x-agent-api-key``
check lives inside the JSON-RPC handler for ``POST /api`` only.

The control plane forwards the source's own signature headers through to the agent
(it strips only hop-by-hop headers), so the agent CAN re-verify them. That is what
this module is for: :class:`WebhookVerification` carries the raw body, the request
headers and the shared secret, and :meth:`WebhookVerification.check` fails closed
unless the signature matches.

Two properties matter and both need the RAW body:

* the HMAC is computed over the exact bytes the source signed -- re-serialising a
  parsed ``dict`` produces different bytes and will never verify;
* Slack additionally binds a timestamp, so a captured request cannot be replayed
  indefinitely.

Stdlib only.
"""

from __future__ import annotations

import hmac
import time
import hashlib
from typing import Literal
from dataclasses import dataclass
from collections.abc import Mapping

__all__ = [
    "GITHUB_SIGNATURE_HEADER",
    "SLACK_MAX_AGE_SECONDS",
    "SLACK_SIGNATURE_HEADER",
    "SLACK_TIMESTAMP_HEADER",
    "WebhookSignatureError",
    "WebhookSource",
    "WebhookVerification",
    "verify_github_signature",
    "verify_slack_signature",
]

WebhookSource = Literal["github", "slack"]

GITHUB_SIGNATURE_HEADER = "x-hub-signature-256"
SLACK_SIGNATURE_HEADER = "x-slack-signature"
SLACK_TIMESTAMP_HEADER = "x-slack-request-timestamp"

# Slack's own guidance: refuse a request whose timestamp is more than five minutes
# old, so a captured body cannot be replayed forever.
SLACK_MAX_AGE_SECONDS = 300


class WebhookSignatureError(RuntimeError):
    """The payload could not be proved to come from the webhook source.

    Deliberately distinct from ``WebhookError``: a handler should answer this with
    401/403, not 500, and must not fall through to driving an agent turn.
    """


def _header(headers: Mapping[str, str], name: str) -> str:
    """Case-insensitive header lookup over a plain mapping.

    Starlette's ``request.headers`` is already case-insensitive, but a handler may
    hand over a plain ``dict``, and HTTP header names are not case-sensitive.
    """
    value = headers.get(name)
    if value is not None:
        return value
    lowered = name.lower()
    for key, candidate in headers.items():
        if isinstance(key, str) and key.lower() == lowered:
            return candidate
    return ""


def verify_github_signature(secret: str, body: bytes, headers: Mapping[str, str]) -> None:
    """Check GitHub's ``X-Hub-Signature-256``; raise :class:`WebhookSignatureError` if bad.

    The signature is ``sha256=<hex>`` of HMAC-SHA256(secret, raw body). Gitea sends
    the same header for the same reason, so this covers both.
    """
    if not secret:
        raise WebhookSignatureError("No webhook secret configured; cannot verify the signature")
    presented = _header(headers, GITHUB_SIGNATURE_HEADER).strip()
    if not presented:
        raise WebhookSignatureError(f"Missing {GITHUB_SIGNATURE_HEADER} header")
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(presented, expected):
        raise WebhookSignatureError(f"Invalid {GITHUB_SIGNATURE_HEADER} signature")


def verify_slack_signature(
    secret: str,
    body: bytes,
    headers: Mapping[str, str],
    *,
    now: float | None = None,
    max_age_seconds: int = SLACK_MAX_AGE_SECONDS,
) -> None:
    """Check Slack's ``X-Slack-Signature``; raise :class:`WebhookSignatureError` if bad.

    The signature is ``v0=<hex>`` of HMAC-SHA256(secret, ``v0:<timestamp>:<raw body>``).
    A timestamp further than ``max_age_seconds`` from now (either direction, so a
    future-dated one is refused too) is rejected before the HMAC is compared.
    """
    if not secret:
        raise WebhookSignatureError("No webhook secret configured; cannot verify the signature")
    presented = _header(headers, SLACK_SIGNATURE_HEADER).strip()
    if not presented:
        raise WebhookSignatureError(f"Missing {SLACK_SIGNATURE_HEADER} header")

    raw_timestamp = _header(headers, SLACK_TIMESTAMP_HEADER).strip()
    try:
        timestamp = int(raw_timestamp)
    except (TypeError, ValueError):
        raise WebhookSignatureError(f"Missing or unparseable {SLACK_TIMESTAMP_HEADER} header") from None
    current = time.time() if now is None else now
    if abs(current - timestamp) > max_age_seconds:
        raise WebhookSignatureError(f"Slack timestamp {timestamp} is more than {max_age_seconds}s from now")

    basis = b"v0:" + raw_timestamp.encode("utf-8") + b":" + body
    expected = "v0=" + hmac.new(secret.encode("utf-8"), basis, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(presented, expected):
        raise WebhookSignatureError(f"Invalid {SLACK_SIGNATURE_HEADER} signature")


@dataclass(frozen=True)
class WebhookVerification:
    """Everything needed to prove one inbound webhook's provenance.

    ``body`` must be the RAW request bytes (``await request.body()``), not a parsed
    and re-serialised dict: the HMAC covers the bytes the source signed.
    """

    source: WebhookSource
    secret: str
    body: bytes
    headers: Mapping[str, str]
    #: Override for tests; ``None`` means ``time.time()`` (Slack freshness only).
    now: float | None = None

    def check(self) -> None:
        """Raise :class:`WebhookSignatureError` unless the signature verifies."""
        if self.source == "github":
            verify_github_signature(self.secret, self.body, self.headers)
        elif self.source == "slack":
            verify_slack_signature(self.secret, self.body, self.headers, now=self.now)
        else:  # pragma: no cover - Literal keeps this unreachable for typed callers
            raise WebhookSignatureError(f"Unknown webhook source {self.source!r}")
