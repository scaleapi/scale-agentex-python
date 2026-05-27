from __future__ import annotations

import dataclasses
from typing import Any

from temporalio.client import Client, Plugin as ClientPlugin
from temporalio.worker import Interceptor
from temporalio.runtime import Runtime, TelemetryConfig, OpenTelemetryConfig
from temporalio.converter import DataConverter, PayloadCodec
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


async def get_temporal_client(
    temporal_address: str,
    metrics_url: str | None = None,
    plugins: list[Any] = [],
    payload_codec: PayloadCodec | None = None,
    data_converter: DataConverter | None = None,
) -> Client:
    """
    Create a Temporal client with plugin integration.

    Args:
        temporal_address: Temporal server address
        metrics_url: Optional metrics endpoint URL
        plugins: List of Temporal plugins to include
        payload_codec: Optional payload codec for encoding/decoding payloads
            (e.g. encryption, compression). Cannot be combined with the
            OpenAIAgentsPlugin via this kwarg — see ``data_converter``.
        data_converter: Optional pre-built ``DataConverter``. Use this when
            composing the OpenAIAgentsPlugin with a payload codec: build a
            ``DataConverter(payload_converter_class=OpenAIPayloadConverter,
            payload_codec=...)`` and pass it here. Mutually exclusive with
            ``payload_codec``.

    Returns:
        Configured Temporal client
    """
    # Validate plugins if any are provided
    if plugins:
        validate_client_plugins(plugins)

    if payload_codec is not None and data_converter is not None:
        raise ValueError(
            "Pass payload_codec inside `data_converter` "
            "(DataConverter(..., payload_codec=...)) instead of as a separate "
            "kwarg. Specifying both is ambiguous."
        )

    # Check if OpenAI plugin is present - it needs to configure its own data converter
    # Lazy import to avoid pulling in opentelemetry.sdk for non-Temporal agents
    from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

    has_openai_plugin = any(isinstance(p, OpenAIAgentsPlugin) for p in (plugins or []))

    # When the OpenAI plugin is present, its `_data_converter` transformer
    # builds a fresh DataConverter (without any codec) if none is supplied,
    # so a standalone `payload_codec` kwarg would be silently dropped and
    # payloads would land in Temporal in plain text. Guide the caller to
    # the working composition path instead.
    if has_openai_plugin and payload_codec is not None and data_converter is None:
        raise ValueError(
            "payload_codec passed as a kwarg alongside OpenAIAgentsPlugin would "
            "be silently dropped by the plugin's data-converter transformer. "
            "Build a DataConverter explicitly with "
            "`payload_converter_class=OpenAIPayloadConverter` (or a subclass) "
            "and `payload_codec=...`, then pass it via the `data_converter` "
            "kwarg instead."
        )

    connect_kwargs: dict[str, Any] = {
        "target_host": temporal_address,
        "plugins": plugins,
    }

    if data_converter is not None:
        # Caller supplied a pre-built converter. With the OpenAI plugin present
        # and `payload_converter_class=OpenAIPayloadConverter` (or subclass),
        # the plugin's `_data_converter` transformer passes it through intact,
        # preserving any payload_codec.
        connect_kwargs["data_converter"] = data_converter
    elif not has_openai_plugin:
        dc = pydantic_data_converter
        if payload_codec:
            dc = dataclasses.replace(dc, payload_codec=payload_codec)
        connect_kwargs["data_converter"] = dc

    if not metrics_url:
        client = await Client.connect(**connect_kwargs)
    else:
        runtime = Runtime(telemetry=TelemetryConfig(metrics=OpenTelemetryConfig(url=metrics_url)))
        connect_kwargs["runtime"] = runtime
        client = await Client.connect(**connect_kwargs)
    return client
