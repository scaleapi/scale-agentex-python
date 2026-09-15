import os
import logging
import contextvars

import ddtrace
import json_log_formatter
from rich.console import Console
from rich.logging import RichHandler

_is_datadog_configured = bool(os.environ.get("DD_AGENT_HOST"))

ctx_var_request_id = contextvars.ContextVar[str]("request_id")

DEFAULT_LOG_LEVEL = logging.INFO

# Every logger this module hands out is a LEAF (``make_logger(__name__)``), and until
# now each one carried its own handler. That is fine on its own, but an observability
# pipeline that owns the ROOT logger -- sgp-obs replaces the root handler list -- then
# prints a SECOND copy of every record: once here, and once more when the record
# propagates to root. Measured on sgp-obs 0.16.0: one ``logger.info()`` produced two
# stdout lines, and sgp-obs' own boot warning named 63 loggers "bypassing log
# governance". The plain-text copy also skips the pipeline's enrichment (agent_id,
# task_id), its allowlist and its truncation, so it is not merely redundant.
#
# While this is True, ``make_logger`` attaches nothing and the record reaches the root
# pipeline by propagation alone. ``sgp_obs_setup`` sets it via
# :func:`route_agentex_loggers_to_root` -- nothing else may.
_ROOT_PIPELINE_OWNS_LOGGING = False

# Handlers are cleared by prefix rather than by an enumerated list: the names are
# module paths, several agentex modules are imported LAZILY, and any list would be a
# snapshot that goes stale the moment one of them loads.
_PACKAGE_ROOT = "agentex"


def resolve_log_level() -> int:
    """Read the log level from ``LOG_LEVEL``, falling back to INFO.

    Read straight from the environment rather than through ``EnvVarKeys``, since
    ``environment_variables`` imports this module and the reverse would be a cycle.

    ``getLevelName`` returns the string ``"Level FOO"`` for anything it does not
    recognise, so the isinstance check is what stops a typo in ``LOG_LEVEL`` from
    silently turning logging off.
    """
    configured = os.getenv("LOG_LEVEL")
    if not configured:
        return DEFAULT_LOG_LEVEL
    level = logging.getLevelName(configured.strip().upper())
    return level if isinstance(level, int) else DEFAULT_LOG_LEVEL


class CustomJSONFormatter(json_log_formatter.JSONFormatter):
    def json_record(self, message: str, extra: dict, record: logging.LogRecord) -> dict:  # type: ignore[override]
        extra = super().json_record(message, extra, record)
        extra["level"] = record.levelname
        extra["name"] = record.name
        extra["lineno"] = record.lineno
        extra["pathname"] = record.pathname
        extra["request_id"] = ctx_var_request_id.get(None)
        if _is_datadog_configured:
            extra["dd.trace_id"] = ddtrace.tracer.get_log_correlation_context().get("dd.trace_id", None) or getattr(  # type: ignore[attr-defined]
                record, "dd.trace_id", 0
            )
            extra["dd.span_id"] = ddtrace.tracer.get_log_correlation_context().get("dd.span_id", None) or getattr(  # type: ignore[attr-defined]
                record, "dd.span_id", 0
            )
        # add the env, service, and version configured for the tracer
        # If tracing is not set up, then this should pull values from DD_ENV, DD_SERVICE, and DD_VERSION.
        service_override = ddtrace.config.service or os.getenv("DD_SERVICE")
        if service_override:
            extra["dd.service"] = service_override

        env_override = ddtrace.config.env or os.getenv("DD_ENV")
        if env_override:
            extra["dd.env"] = env_override

        version_override = ddtrace.config.version or os.getenv("DD_VERSION")
        if version_override:
            extra["dd.version"] = version_override

        return extra

def make_logger(name: str) -> logging.Logger:
    """
    Creates a logger object with a RichHandler to print colored text.
    :param name: The name of the module to create the logger for.
    :return: A logger object.
    """
    # Create a console object to print colored text
    logger = logging.getLogger(name)
    logger.setLevel(resolve_log_level())

    if _ROOT_PIPELINE_OWNS_LOGGING:
        # A handler here would be the second one on this record's path to stdout.
        # The level above is deliberately still applied: LOG_LEVEL is what agent
        # authors set, and letting the pipeline's own threshold silently replace it
        # would change behaviour nobody asked to change.
        return logger

    environment = os.getenv("ENVIRONMENT")
    if environment == "local":
        console = Console()
        # Add the RichHandler to the logger to print colored text
        handler = RichHandler(
            console=console,
            show_level=False,
            show_path=False,
            show_time=False,
        )
        logger.addHandler(handler)
        return logger

    stream_handler = logging.StreamHandler()
    if _is_datadog_configured:
        stream_handler.setFormatter(CustomJSONFormatter())
    else:
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] - %(message)s")
        )

    logger.addHandler(stream_handler)
    # Create a logger object with the name of the current module
    return logger


def route_agentex_loggers_to_root() -> int:
    """Hand agentex's logging over to whatever owns the root logger. Returns the
    number of loggers cleared.

    Two halves, and BOTH are needed -- measured, one line per ``logger.info()`` only
    when they run together:

    * the sweep below fixes the loggers that ALREADY exist, i.e. every agentex module
      imported before this ran;
    * the flag fixes every logger created AFTER it, which a sweep cannot reach.
      agentex imports several modules lazily (the adk ``_claude_code_sync`` /
      ``_codex_sync`` / ``_pydantic_ai_sync`` harnesses among them), so their
      ``make_logger`` call happens later and would attach a fresh duplicate handler.

    sgp-obs offers ``capture_loggers=`` for the first half, and it is deliberately not
    used: it matches EXACT logger names, not prefixes (measured -- passing
    ``("agentex",)`` still produced two lines), so it would mean enumerating ~60 module
    paths; and passing anything at all replaces its uvicorn default, which would put
    uvicorn's access log back to printing twice.

    Only agentex's own loggers are touched. A third party's handler may be there on
    purpose -- which is exactly why sgp-obs warns about them rather than stripping them
    -- so litellm's three loggers and anything else keep whatever they have.
    """
    global _ROOT_PIPELINE_OWNS_LOGGING
    _ROOT_PIPELINE_OWNS_LOGGING = True

    cleared = 0
    # list() snapshots the registry: a getLogger() on another thread would otherwise
    # mutate the dict mid-iteration.
    for name, existing in list(logging.Logger.manager.loggerDict.items()):
        if not isinstance(existing, logging.Logger):
            continue  # a PlaceHolder for a name whose children exist but itself does not
        if name != _PACKAGE_ROOT and not name.startswith(_PACKAGE_ROOT + "."):
            continue
        if not existing.handlers:
            continue
        if not existing.propagate:
            # Deliberately cut off from root, so nothing of its reaches the pipeline.
            # Clearing its handlers would send its records NOWHERE -- worse than a
            # duplicate. Leave it exactly as its owner set it up.
            continue
        for handler in list(existing.handlers):
            try:
                handler.flush()  # a buffering handler must not lose records on removal
            except Exception:
                pass
            existing.removeHandler(handler)
        cleared += 1
    return cleared


def _reset_for_tests() -> None:
    global _ROOT_PIPELINE_OWNS_LOGGING
    _ROOT_PIPELINE_OWNS_LOGGING = False
