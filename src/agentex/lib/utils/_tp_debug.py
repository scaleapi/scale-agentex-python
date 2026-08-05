# TEMP(obs-debug): remove after diagnosing async-trace propagation.
# Logs the W3C traceparent derived from the CURRENT active OpenTelemetry context
# at each hop of the ACP ingress -> Temporal start/signal -> workflow -> activity
# chain, so we can see exactly where the trace context is dropped. Grep the agent
# logs for "[TP-DEBUG]".
from __future__ import annotations

from agentex.lib.utils.logging import make_logger

logger = make_logger("tp_debug")


def active_traceparent() -> str:
    """W3C traceparent for the current active OTel context, or a marker string."""
    try:
        from opentelemetry.propagate import inject

        carrier: dict[str, str] = {}
        inject(carrier)
        return carrier.get("traceparent", "<none>")
    except Exception as exc:  # pragma: no cover - debug only
        return f"<err:{exc}>"


def log_tp(where: str, **extra: object) -> None:
    """Emit a one-line [TP-DEBUG] log: where + current traceparent + any extras."""
    kv = " ".join(f"{k}={v}" for k, v in extra.items())
    logger.info("[TP-DEBUG] %s traceparent=%s %s", where, active_traceparent(), kv)
