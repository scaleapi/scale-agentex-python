# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type
from agentex.types.messages import BatchCreateResponse, BatchUpdateResponse

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestBatch:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_create(self, client: Agentex) -> None:
        batch = client.messages.batch.create(
            contents=[
                {
                    "author": "user",
                    "content": "content",
                }
            ],
            task_id="task_id",
        )
        assert_matches_type(BatchCreateResponse, batch, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_create(self, client: Agentex) -> None:
        response = client.messages.batch.with_raw_response.create(
            contents=[
                {
                    "author": "user",
                    "content": "content",
                }
            ],
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        batch = response.parse()
        assert_matches_type(BatchCreateResponse, batch, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_create(self, client: Agentex) -> None:
        with client.messages.batch.with_streaming_response.create(
            contents=[
                {
                    "author": "user",
                    "content": "content",
                }
            ],
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            batch = response.parse()
            assert_matches_type(BatchCreateResponse, batch, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_method_update(self, client: Agentex) -> None:
        batch = client.messages.batch.update(
            task_id="task_id",
            updates={
                "foo": {
                    "author": "user",
                    "content": "content",
                }
            },
        )
        assert_matches_type(BatchUpdateResponse, batch, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_raw_response_update(self, client: Agentex) -> None:
        response = client.messages.batch.with_raw_response.update(
            task_id="task_id",
            updates={
                "foo": {
                    "author": "user",
                    "content": "content",
                }
            },
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        batch = response.parse()
        assert_matches_type(BatchUpdateResponse, batch, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    def test_streaming_response_update(self, client: Agentex) -> None:
        with client.messages.batch.with_streaming_response.update(
            task_id="task_id",
            updates={
                "foo": {
                    "author": "user",
                    "content": "content",
                }
            },
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            batch = response.parse()
            assert_matches_type(BatchUpdateResponse, batch, path=["response"])

        assert cast(Any, response.is_closed) is True


class TestAsyncBatch:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_create(self, async_client: AsyncAgentex) -> None:
        batch = await async_client.messages.batch.create(
            contents=[
                {
                    "author": "user",
                    "content": "content",
                }
            ],
            task_id="task_id",
        )
        assert_matches_type(BatchCreateResponse, batch, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_create(self, async_client: AsyncAgentex) -> None:
        response = await async_client.messages.batch.with_raw_response.create(
            contents=[
                {
                    "author": "user",
                    "content": "content",
                }
            ],
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        batch = await response.parse()
        assert_matches_type(BatchCreateResponse, batch, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_create(self, async_client: AsyncAgentex) -> None:
        async with async_client.messages.batch.with_streaming_response.create(
            contents=[
                {
                    "author": "user",
                    "content": "content",
                }
            ],
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            batch = await response.parse()
            assert_matches_type(BatchCreateResponse, batch, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_method_update(self, async_client: AsyncAgentex) -> None:
        batch = await async_client.messages.batch.update(
            task_id="task_id",
            updates={
                "foo": {
                    "author": "user",
                    "content": "content",
                }
            },
        )
        assert_matches_type(BatchUpdateResponse, batch, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_raw_response_update(self, async_client: AsyncAgentex) -> None:
        response = await async_client.messages.batch.with_raw_response.update(
            task_id="task_id",
            updates={
                "foo": {
                    "author": "user",
                    "content": "content",
                }
            },
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        batch = await response.parse()
        assert_matches_type(BatchUpdateResponse, batch, path=["response"])

    @pytest.mark.skip(reason="Prism tests are disabled")
    @parametrize
    async def test_streaming_response_update(self, async_client: AsyncAgentex) -> None:
        async with async_client.messages.batch.with_streaming_response.update(
            task_id="task_id",
            updates={
                "foo": {
                    "author": "user",
                    "content": "content",
                }
            },
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            batch = await response.parse()
            assert_matches_type(BatchUpdateResponse, batch, path=["response"])

        assert cast(Any, response.is_closed) is True
