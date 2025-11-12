from __future__ import annotations

from typing import Any

from temporalio.client import Client, Plugin as ClientPlugin
from temporalio.worker import Interceptor
from temporalio.runtime import Runtime, TelemetryConfig, OpenTelemetryConfig
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

# class DateTimeJSONEncoder(AdvancedJSONEncoder):
#     def default(self, o: Any) -> Any:
#         if isinstance(o, datetime.datetime):
#             return o.isoformat()
#         return super().default(o)


# class DateTimeJSONTypeConverter(JSONTypeConverter):
#     def to_typed_value(
#         self, hint: Type, value: Any
#     ) -> Union[Optional[Any], _JSONTypeConverterUnhandled]:
#         if hint == datetime.datetime:
#             return datetime.datetime.fromisoformat(value)
#         return JSONTypeConverter.Unhandled


# class DateTimePayloadConverter(CompositePayloadConverter):
#     def __init__(self) -> None:
#         json_converter = JSONPlainPayloadConverter(
#             encoder=DateTimeJSONEncoder,
#             custom_type_converters=[DateTimeJSONTypeConverter()],
#         )
#         super().__init__(
#             *[
#                 c if not isinstance(c, JSONPlainPayloadConverter) else json_converter
#                 for c in DefaultPayloadConverter.default_encoding_payload_converters
#             ]
#         )


# custom_data_converter = dataclasses.replace(
#     DataConverter.default,
#     payload_converter_class=DateTimePayloadConverter,
# )


def validate_client_plugins(plugins: list[Any]) -> None:
    """
    Validate that all items in the plugins list are valid Temporal client plugins.

    Args:
        plugins: List of plugins to validate

    Raises:
        TypeError: If any plugin is not a valid ClientPlugin instance
    """
    for i, plugin in enumerate(plugins):
        if not isinstance(plugin, ClientPlugin):
            raise TypeError(
                f"Plugin at index {i} must be an instance of temporalio.client.Plugin, "
                f"got {type(plugin).__name__}. Note: WorkerPlugin is not valid for workflow clients."
            )


def validate_worker_interceptors(interceptors: list[Any]) -> None:
    """
    Validate that all items in the interceptors list are valid Temporal worker interceptors.

    Args:
        interceptors: List of interceptors to validate

    Raises:
        TypeError: If any interceptor is not a valid Interceptor instance
    """
    for i, interceptor in enumerate(interceptors):
        if not isinstance(interceptor, Interceptor):
            raise TypeError(
                f"Interceptor at index {i} must be an instance of temporalio.worker.Interceptor, "
                f"got {type(interceptor).__name__}"
            )


async def get_temporal_client(temporal_address: str, metrics_url: str | None = None, plugins: list[Any] = []) -> Client:
    """
    Create a Temporal client with plugin integration.

    Args:
        temporal_address: Temporal server address
        metrics_url: Optional metrics endpoint URL
        plugins: List of Temporal plugins to include

    Returns:
        Configured Temporal client
    """
    # Validate plugins if any are provided
    if plugins:
        validate_client_plugins(plugins)

    # Check if OpenAI plugin is present - it needs to configure its own data converter
    has_openai_plugin = any(
        isinstance(p, OpenAIAgentsPlugin) for p in (plugins or [])
    )

    # Only set data_converter if OpenAI plugin is not present
    connect_kwargs = {
        "target_host": temporal_address,
        "plugins": plugins,
    }

    if not has_openai_plugin:
        connect_kwargs["data_converter"] = pydantic_data_converter

    if not metrics_url:
        client = await Client.connect(**connect_kwargs)
    else:
        runtime = Runtime(telemetry=TelemetryConfig(metrics=OpenTelemetryConfig(url=metrics_url)))
        connect_kwargs["runtime"] = runtime
        client = await Client.connect(**connect_kwargs)
    return client
