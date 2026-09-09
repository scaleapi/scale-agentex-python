from __future__ import annotations

import json

import httpx
import respx
import pytest

from agentex import Agentex, AsyncAgentex
from agentex.lib.utils.metadata_filters import encode_metadata_filter

BASE_URL = "http://127.0.0.1:4010"
API_KEY = "My API Key"


class TestEncodeMetadataFilter:
    def test_encodes_a_json_object(self) -> None:
        assert encode_metadata_filter({"permits_capable": True}) == '{"permits_capable":true}'

    def test_empty_mapping_encodes_to_an_empty_object(self) -> None:
        assert encode_metadata_filter({}) == "{}"

    def test_key_order_is_stable(self) -> None:
        assert (
            encode_metadata_filter({"region": "us", "permits_capable": True})
            == encode_metadata_filter({"permits_capable": True, "region": "us"})
            == '{"permits_capable":true,"region":"us"}'
        )

    def test_preserves_json_types_and_nesting(self) -> None:
        encoded = encode_metadata_filter({"flag": True, "count": 3, "ratio": 1.5, "nested": {"a": [1, "two", None]}})
        assert json.loads(encoded) == {
            "flag": True,
            "count": 3,
            "ratio": 1.5,
            "nested": {"a": [1, "two", None]},
        }

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_non_finite_floats(self, value: float) -> None:
        # The server rejects these with a 400; fail locally with a clearer message.
        with pytest.raises(ValueError, match="not encodable as JSON"):
            encode_metadata_filter({"x": value})

    def test_rejects_a_non_mapping(self) -> None:
        with pytest.raises(TypeError, match="must be a mapping"):
            encode_metadata_filter([("permits_capable", True)])  # type: ignore[arg-type]

    def test_rejects_a_non_serializable_value(self) -> None:
        with pytest.raises(TypeError):
            encode_metadata_filter({"x": object()})


class TestAgentCardMetadataOnTheWire:
    """The encoded filter has to survive the client's query-string serialization.

    The generated `agents.list` parameter is a plain `str` (the platform spec
    declares a JSON-encoded string, matching the shipped `task_metadata`
    filter), so these assert the exact query value the server will parse.
    """

    @respx.mock(base_url=BASE_URL)
    def test_sync_client_sends_the_encoded_object(self, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/agents").mock(return_value=httpx.Response(200, json=[]))

        with Agentex(base_url=BASE_URL, api_key=API_KEY, _strict_response_validation=True) as client:
            client.agents.list(
                agent_card_metadata=encode_metadata_filter({"permits_capable": True, "region": "us"}),
                limit=5,
            )

        params = route.calls.last.request.url.params
        raw = params["agent_card_metadata"]
        assert raw == '{"permits_capable":true,"region":"us"}'
        assert json.loads(raw) == {"permits_capable": True, "region": "us"}
        assert params["limit"] == "5"

    @respx.mock(base_url=BASE_URL)
    async def test_async_client_sends_the_encoded_object(self, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/agents").mock(return_value=httpx.Response(200, json=[]))

        async with AsyncAgentex(base_url=BASE_URL, api_key=API_KEY, _strict_response_validation=True) as client:
            await client.agents.list(
                agent_card_metadata=encode_metadata_filter({"permits_capable": True, "region": "us"}),
                limit=5,
            )

        params = route.calls.last.request.url.params
        raw = params["agent_card_metadata"]
        assert raw == '{"permits_capable":true,"region":"us"}'
        assert json.loads(raw) == {"permits_capable": True, "region": "us"}
        assert params["limit"] == "5"

    @respx.mock(base_url=BASE_URL)
    def test_omitted_filter_is_absent_from_the_query(self, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/agents").mock(return_value=httpx.Response(200, json=[]))

        with Agentex(base_url=BASE_URL, api_key=API_KEY, _strict_response_validation=True) as client:
            client.agents.list()

        assert "agent_card_metadata" not in route.calls.last.request.url.params

    @respx.mock(base_url=BASE_URL)
    def test_empty_object_filter_is_sent_verbatim(self, respx_mock: respx.MockRouter) -> None:
        """`{}` is a meaningful filter server-side (agent must have card metadata),
        so it must reach the wire rather than being dropped as falsy."""
        route = respx_mock.get("/agents").mock(return_value=httpx.Response(200, json=[]))

        with Agentex(base_url=BASE_URL, api_key=API_KEY, _strict_response_validation=True) as client:
            client.agents.list(agent_card_metadata=encode_metadata_filter({}))

        assert route.calls.last.request.url.params["agent_card_metadata"] == "{}"
