from typing import Any

from temporalio.client import Client, Plugin as ClientPlugin
from temporalio.runtime import Runtime, TelemetryConfig, OpenTelemetryConfig
from temporalio.contrib.pydantic import pydantic_data_converter

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

    if not metrics_url:
        client = await Client.connect(
            target_host=temporal_address,
            # data_converter=custom_data_converter,
            data_converter=pydantic_data_converter,
            plugins=plugins,
        )
    else:
        runtime = Runtime(telemetry=TelemetryConfig(metrics=OpenTelemetryConfig(url=metrics_url)))
        client = await Client.connect(
            target_host=temporal_address,
            # data_converter=custom_data_converter,
            data_converter=pydantic_data_converter,
            runtime=runtime,
            plugins=plugins,
        )
    return client
