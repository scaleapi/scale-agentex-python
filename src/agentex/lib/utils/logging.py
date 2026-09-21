import os
import logging
import contextvars

import ddtrace
import json_log_formatter
from rich.console import Console
from rich.logging import RichHandler

_is_datadog_configured = bool(os.environ.get("DD_AGENT_HOST"))

ctx_var_request_id = contextvars.ContextVar[str]("request_id")


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
    logger.setLevel(logging.INFO)

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
