# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestClient:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip()
    @parametrize
    def test_method_get_root(self, client: Agentex) -> None:
        client_ = client.get_root()
        assert_matches_type(object, client_, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_raw_response_get_root(self, client: Agentex) -> None:
        response = client.with_raw_response.get_root()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        client_ = response.parse()
        assert_matches_type(object, client_, path=["response"])

    @pytest.mark.skip()
    @parametrize
    def test_streaming_response_get_root(self, client: Agentex) -> None:
        with client.with_streaming_response.get_root() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            client_ = response.parse()
            assert_matches_type(object, client_, path=["response"])

        assert cast(Any, response.is_closed) is True


class TestAsyncClient:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip()
    @parametrize
    async def test_method_get_root(self, async_client: AsyncAgentex) -> None:
        client = await async_client.get_root()
        assert_matches_type(object, client, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_raw_response_get_root(self, async_client: AsyncAgentex) -> None:
        response = await async_client.with_raw_response.get_root()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        client = await response.parse()
        assert_matches_type(object, client, path=["response"])

    @pytest.mark.skip()
    @parametrize
    async def test_streaming_response_get_root(self, async_client: AsyncAgentex) -> None:
        async with async_client.with_streaming_response.get_root() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            client = await response.parse()
            assert_matches_type(object, client, path=["response"])

        assert cast(Any, response.is_closed) is True
