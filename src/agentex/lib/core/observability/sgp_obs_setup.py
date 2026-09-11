"""Optional sgp-obs wiring: traces, metrics and logs, switched on by environment.

Why this lives in the SDK rather than in each agent: the fleet is ~147 agent repos,
and their deployments pin an exact SDK version. Doing the wiring here means an agent
adopts observability by installing ``sgp-obs`` and setting environment, instead of
carrying the wiring code — including the two parts that are easy to get wrong and
fail silently (where ``init()`` is called from, and flushing on the way out).

``sgp-obs`` is NOT declared as a dependency or an extra of this package. It is not on
public PyPI, and declaring it would make this repo's own uv workspace unresolvable:
``uv sync`` re-locks, locking must resolve every declared optional dependency, and
neither ``--no-extra`` nor ``[tool.uv] override-dependencies`` exempts one. So the
contract is inverted — an agent declares ``sgp-obs[genai-auto,http,otlp]`` itself,
against Scale's curated mirror, and this module wires it if it is importable. Nothing
here imports ``sgp_obs`` outside a ``try``, so a plain ``pip install agentex-sdk``
behaves exactly as it did before this module existed.

TWO gates, both of which must pass before anything is recorded:

1. ``sgp-obs`` must be importable. If it is not, this returns ``"not_installed"``.
2. The environment must ask for it. As of sgp-obs 0.16.0 every signal is opt-in
   TWICE: the master switch ``SGP_OBS_ENABLED=true``, AND that signal's
   ``*_DISABLED`` variable set to an explicit ``false``. An unset ``*_DISABLED``
   leaves the signal OFF. So the master switch on its own wires nothing at all —
   measured on 0.16.0, ``SGP_OBS_ENABLED=true`` alone returns zero handles. All
   three signals together need::

       SGP_OBS_ENABLED=true
       SGP_METRICS_DISABLED=false
       SGP_TRACES_DISABLED=false
       SGP_LOGS_DISABLED=false

   That inverts the advice written against 0.15.0, where traces came on with the
   master switch and had to be turned off. This module does not second-guess the
   gate — it calls ``init()`` and reports which signals came back — but it does
   warn when the master switch is on and nothing wired, because that combination
   is otherwise completely silent.

Metrics additionally need an OTLP endpoint. sgp-obs never builds a MeterProvider
from nothing; in a cluster the OTel Operator's auto-instrumentation normally
supplies one, and agent pods get no injection, so ``OTEL_EXPORTER_OTLP_ENDPOINT``
has to be on the pod spec.

Fail-open is absolute: this is telemetry, and no failure here may stop an agent from
starting or serving. Every path returns a status string instead of raising.
"""

from __future__ import annotations

import os
from typing import Any

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

_status: str | None = None

# sgp-obs' own truthy set (sgp_obs.env._TRUTHY), so "is the master switch on?" is
# answered the same way here as in the library deciding whether to wire.
_TRUTHY = {"1", "true", "yes", "on"}

# The logs-profile selector. The SDK knows the runtime is agentex; an agent author
# would have to know to pass it. It stamps agent_id (from AGENT_ID) and task_id (from
# the SDK's streaming contextvar) onto every log record.
_SOURCE = "agentex"


def _master_switch_on() -> bool:
    return (os.getenv("SGP_OBS_ENABLED") or "").strip().lower() in _TRUTHY


def init_sgp_obs(app: Any = None) -> str:
    """Wire sgp-obs if it is installed and enabled. Returns a status; never raises.

    Statuses: ``"not_installed"``, ``"disabled"``, ``"wired:<signals>"``, ``"error"``.

    ``app`` is the ACP server. Passing it is what adds ``http.server.*`` for the
    agent's own entry point — without it the agent is observable only from the
    model call outwards, and its own latency and error rate cannot be alerted on.
    It is also what installs the trace-context ingress middleware, so an incoming
    ``traceparent`` continues into the agent's spans rather than starting a new trace.
    """
    global _status
    if _status is not None:
        # init() is not meant to run twice, and a Temporal worker plus an ACP
        # server can both reach this in one process.
        return _status

    try:
        # Not resolvable in a normal env: sgp-obs is not a dependency of this
        # package and is not on public PyPI. That is the case this branch exists for.
        import sgp_obs  # type: ignore[import-not-found]
    except ImportError:
        if _master_switch_on():
            # The operator asked for observability and the package is absent. Silence
            # here is the worst outcome, so say what is missing and how to fix it.
            logger.warning(
                "SGP_OBS_ENABLED is set but sgp-obs is not installed, so no telemetry "
                "will be produced. Add sgp-obs[genai-auto,http,otlp] to this agent's "
                "dependencies (it resolves from Scale's curated mirror, not public PyPI)."
            )
        _status = "not_installed"
        return _status
    except Exception:  # pragma: no cover - a broken install must not stop startup
        logger.debug("sgp-obs import failed unexpectedly", exc_info=True)
        _status = "error"
        return _status

    try:
        handles = sgp_obs.init(
            app=app,
            # Fills OTEL_SERVICE_NAME only when the deployment left it unset or
            # blank; the deployment always outranks this. Without either, every
            # signal is attributed to service.name="unknown".
            service_name=(os.getenv("AGENT_NAME") or "").strip() or None,
            source=_SOURCE,
        )
    except Exception:  # pragma: no cover - sgp_obs.init is itself fail-open
        # One deliberate exception to its fail-open rule: under the standard CI
        # variable, any logs misconfiguration raises so a build cannot pass while
        # logging is broken. Swallowed here regardless — an agent must still serve.
        logger.warning("sgp-obs initialization failed; continuing without it", exc_info=True)
        _status = "error"
        return _status

    if not handles:
        if _master_switch_on():
            # 0.16.0's double opt-in: the master switch alone wires nothing, and
            # sgp-obs says nothing about it. Name the variables that are missing.
            logger.warning(
                "SGP_OBS_ENABLED is set but no sgp-obs signal is enabled, so nothing "
                "will be exported. Each signal is opt-in separately: set "
                "SGP_METRICS_DISABLED=false, SGP_TRACES_DISABLED=false and "
                "SGP_LOGS_DISABLED=false for the signals you want. An unset "
                "*_DISABLED leaves that signal off."
            )
        # Otherwise expected, and the default: an agent with sgp-obs installed still
        # records nothing until someone sets the environment.
        _status = "disabled"
        return _status

    _status = "wired:" + ",".join(sorted(handles))
    logger.info("sgp-obs wired (%s)", _status)
    return _status


async def shutdown_sgp_obs() -> None:
    """Flush the providers ``init()`` built. Never raises.

    Without this, whatever is sitting in a periodic exporter's buffer when the pod
    stops is dropped — which for a short-lived or scaled-to-zero agent can be most
    of what it recorded. sgp-obs only flushes providers it OWNS; one adopted from
    the runtime is left to its owner, so this is safe under operator injection.

    Run in a thread: the flush blocks up to the SDK export timeout per owned signal,
    and this is called from an async lifespan.
    """
    if _status is None or not _status.startswith("wired"):
        return

    try:
        import asyncio

        import sgp_obs  # type: ignore[import-not-found]

        # Added in sgp-obs 0.16.0. Feature-detected rather than version-pinned,
        # because this package does not depend on sgp-obs and so cannot set a floor.
        shutdown = getattr(sgp_obs, "shutdown", None)
        if shutdown is None:
            logger.debug("sgp-obs has no shutdown(); needs 0.16.0+ to flush on exit")
            return
        await asyncio.to_thread(shutdown)
    except Exception:  # pragma: no cover - a failed flush must not fail shutdown
        logger.debug("sgp-obs shutdown failed", exc_info=True)


def _reset_for_tests() -> None:
    global _status
    _status = None
