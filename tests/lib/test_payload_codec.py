from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from temporalio.client import Client, Plugin as ClientPlugin
from temporalio.converter import PayloadCodec
from temporalio.contrib.pydantic import pydantic_data_converter


class _NoopCodec(PayloadCodec):
    async def encode(self, payloads):
        return list(payloads)

    async def decode(self, payloads):
        return list(payloads)


class _FakeOpenAIPlugin(ClientPlugin):
    def configure_client(self, config):
        return config

    async def connect_service_client(self, config, next):
        return await next(config)


def _mock_connect():
    return patch.object(Client, "connect", new=AsyncMock(return_value=object()))


def _patch_openai_plugin():
    return patch("temporalio.contrib.openai_agents.OpenAIAgentsPlugin", _FakeOpenAIPlugin)


class TestTemporalClient:
    def test_init_stores_payload_codec(self):
        from agentex.lib.core.clients.temporal.temporal_client import TemporalClient

        codec = _NoopCodec()
        client = TemporalClient(payload_codec=codec)
        assert client._payload_codec is codec

    def test_init_default_payload_codec_is_none(self):
        from agentex.lib.core.clients.temporal.temporal_client import TemporalClient

        assert TemporalClient()._payload_codec is None

    async def test_create_with_disabled_address_stores_codec(self):
        from agentex.lib.core.clients.temporal.temporal_client import TemporalClient

        codec = _NoopCodec()
        client = await TemporalClient.create(temporal_address="false", payload_codec=codec)
        assert client._client is None
        assert client._payload_codec is codec

    async def test_create_propagates_codec_to_get_temporal_client(self):
        import agentex.lib.core.clients.temporal.temporal_client as module

        codec = _NoopCodec()
        with patch.object(module, "get_temporal_client", new=AsyncMock(return_value=object())) as mock_get:
            await module.TemporalClient.create(temporal_address="localhost:7233", plugins=[], payload_codec=codec)

        mock_get.assert_awaited_once()
        assert mock_get.await_args.kwargs["payload_codec"] is codec


class TestGetTemporalClientUtils:
    async def test_no_codec_uses_pydantic_data_converter_unchanged(self):
        from agentex.lib.core.clients.temporal.utils import get_temporal_client

        with _mock_connect() as mock_connect:
            await get_temporal_client(temporal_address="localhost:7233")

        kwargs = mock_connect.await_args.kwargs
        assert kwargs["data_converter"] is pydantic_data_converter
        assert kwargs["data_converter"].payload_codec is None

    async def test_codec_is_attached_to_pydantic_data_converter(self):
        from agentex.lib.core.clients.temporal.utils import get_temporal_client

        codec = _NoopCodec()
        with _mock_connect() as mock_connect:
            await get_temporal_client(temporal_address="localhost:7233", payload_codec=codec)

        data_converter = mock_connect.await_args.kwargs["data_converter"]
        assert data_converter.payload_codec is codec
        assert data_converter.payload_converter_class is pydantic_data_converter.payload_converter_class

    async def test_codec_with_openai_plugin_raises(self):
        from agentex.lib.core.clients.temporal.utils import get_temporal_client

        codec = _NoopCodec()
        with _patch_openai_plugin(), _mock_connect() as mock_connect:
            with pytest.raises(ValueError, match="payload_codec is not supported alongside OpenAIAgentsPlugin"):
                await get_temporal_client(
                    temporal_address="localhost:7233",
                    plugins=[_FakeOpenAIPlugin()],
                    payload_codec=codec,
                )
            mock_connect.assert_not_awaited()

    async def test_openai_plugin_without_codec_omits_data_converter(self):
        from agentex.lib.core.clients.temporal.utils import get_temporal_client

        with _patch_openai_plugin(), _mock_connect() as mock_connect:
            await get_temporal_client(temporal_address="localhost:7233", plugins=[_FakeOpenAIPlugin()])

        assert "data_converter" not in mock_connect.await_args.kwargs


class TestGetTemporalClientWorker:
    async def test_no_codec_uses_custom_data_converter_unchanged(self):
        from agentex.lib.core.temporal.workers.worker import get_temporal_client, custom_data_converter

        with _mock_connect() as mock_connect:
            await get_temporal_client(temporal_address="localhost:7233")

        kwargs = mock_connect.await_args.kwargs
        assert kwargs["data_converter"] is custom_data_converter
        assert kwargs["data_converter"].payload_codec is None

    async def test_codec_is_attached_to_custom_data_converter(self):
        from agentex.lib.core.temporal.workers.worker import get_temporal_client, custom_data_converter

        codec = _NoopCodec()
        with _mock_connect() as mock_connect:
            await get_temporal_client(temporal_address="localhost:7233", payload_codec=codec)

        data_converter = mock_connect.await_args.kwargs["data_converter"]
        assert data_converter.payload_codec is codec
        assert data_converter.payload_converter_class is custom_data_converter.payload_converter_class

    async def test_codec_with_openai_plugin_raises(self):
        from agentex.lib.core.temporal.workers.worker import get_temporal_client

        codec = _NoopCodec()
        with _patch_openai_plugin(), _mock_connect() as mock_connect:
            with pytest.raises(ValueError, match="payload_codec is not supported alongside OpenAIAgentsPlugin"):
                await get_temporal_client(
                    temporal_address="localhost:7233",
                    plugins=[_FakeOpenAIPlugin()],
                    payload_codec=codec,
                )
            mock_connect.assert_not_awaited()

    async def test_openai_plugin_without_codec_omits_data_converter(self):
        from agentex.lib.core.temporal.workers.worker import get_temporal_client

        with _patch_openai_plugin(), _mock_connect() as mock_connect:
            await get_temporal_client(temporal_address="localhost:7233", plugins=[_FakeOpenAIPlugin()])

        assert "data_converter" not in mock_connect.await_args.kwargs


class TestAgentexWorkerCodec:
    def test_worker_stores_payload_codec(self):
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        codec = _NoopCodec()
        worker = AgentexWorker(task_queue="test-queue", health_check_port=80, payload_codec=codec)
        assert worker.payload_codec is codec

    def test_worker_default_payload_codec_is_none(self):
        from agentex.lib.core.temporal.workers.worker import AgentexWorker

        worker = AgentexWorker(task_queue="test-queue", health_check_port=80)
        assert worker.payload_codec is None


class TestTemporalACPCodec:
    def test_create_stores_payload_codec(self):
        from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP

        codec = _NoopCodec()
        acp = TemporalACP.create(temporal_address="localhost:7233", payload_codec=codec)
        assert acp._payload_codec is codec

    def test_create_default_payload_codec_is_none(self):
        from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP

        acp = TemporalACP.create(temporal_address="localhost:7233")
        assert acp._payload_codec is None


class TestFastACPConfigCodec:
    def test_config_default_codec_is_none(self):
        from agentex.lib.types.fastacp import TemporalACPConfig

        assert TemporalACPConfig().payload_codec is None

    def test_config_accepts_codec(self):
        from agentex.lib.types.fastacp import TemporalACPConfig

        codec = _NoopCodec()
        assert TemporalACPConfig(payload_codec=codec).payload_codec is codec

    def test_fastacp_forwards_codec_from_config(self):
        from agentex.lib.types.fastacp import TemporalACPConfig
        from agentex.lib.sdk.fastacp.fastacp import FastACP

        codec = _NoopCodec()
        config = TemporalACPConfig(payload_codec=codec)
        captured: dict[str, Any] = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return object()

        with patch(
            "agentex.lib.sdk.fastacp.impl.temporal_acp.TemporalACP.create",
            side_effect=fake_create,
        ):
            FastACP.create("async", config=config)

        assert captured.get("payload_codec") is codec
