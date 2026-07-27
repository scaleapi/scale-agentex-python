"""OTel metrics for event delivery (task/event_send -> live workflow).

Records whether an EVENT_SEND signal actually reached a *running* Temporal
workflow, vs. only being accepted by the ACP server. ``event/send`` is async:
the ACP server returns a 200 ack before the signal is even attempted (see
``base_acp_server._handle_jsonrpc`` background branch), so HTTP status is not a
delivery signal — this counter is. Under load, tasks that have already
completed or idle-timed-out have no workflow to receive the event, which
Temporal surfaces as an ``RPCError`` with status ``NOT_FOUND``.

The meter is no-op when the application hasn't configured a ``MeterProvider``,
so importing this module is safe for runtimes that don't use OTel. Instruments
are created lazily on first ``get_event_metrics()`` call so a ``MeterProvider``
configured *after* this module is imported still binds correctly.

Recording is gated on ``AGENTEX_EVENT_METRICS`` (default on) and every record
is best-effort — it never raises into the business path.

Cardinality is bounded: the only attribute is ``outcome``, drawn from a small
fixed set (see the ``OUTCOME_*`` constants). Resource attributes
(``service.name``, ``k8s.*``, etc.) come from the application's OTel resource
configuration and are added to every series automatically.
"""

from __future__ import annotations

import os
from typing import Optional

from opentelemetry import metrics

# Outcome label values (bounded cardinality — do NOT add task IDs etc.).
OUTCOME_DELIVERED = "delivered"
OUTCOME_NO_LIVE_WORKFLOW = "no_live_workflow"
OUTCOME_ERROR = "error"


class EventMetrics:
    """Lazily-created OTel instruments for event-delivery telemetry."""

    def __init__(self) -> None:
        meter = metrics.get_meter("agentex.events")
        self.delivery = meter.create_counter(
            name="agentex.events.delivery",
            unit="1",
            description=(
                "task/event_send deliveries tagged with outcome (delivered / "
                "no_live_workflow / error). 'no_live_workflow' means the signal "
                "had no running workflow to receive it (task already completed "
                "or idle-timed-out). Use delivered / (delivered + "
                "no_live_workflow) as the true event-delivery rate."
            ),
        )


_event_metrics: Optional[EventMetrics] = None


def get_event_metrics() -> EventMetrics:
    """Return the event metrics singleton, creating it on first use."""
    global _event_metrics
    if _event_metrics is None:
        _event_metrics = EventMetrics()
    return _event_metrics


_metrics_enabled: Optional[bool] = None


def is_event_metrics_enabled() -> bool:
    """Whether event-delivery metric recording is enabled (AGENTEX_EVENT_METRICS)."""
    global _metrics_enabled
    if _metrics_enabled is None:
        raw = os.environ.get("AGENTEX_EVENT_METRICS", "1").strip().lower()
        _metrics_enabled = raw not in ("0", "false", "no", "off")
    return _metrics_enabled


def record_event_delivery(outcome: str) -> None:
    """Best-effort bump of the event-delivery counter for the given outcome.

    ``outcome`` should be one of the ``OUTCOME_*`` constants.
    """
    if not is_event_metrics_enabled():
        return
    try:
        get_event_metrics().delivery.add(1, {"outcome": outcome})
    except Exception:
        pass
