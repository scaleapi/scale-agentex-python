# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, Optional, cast

import pytest

from agentex import Agentex, AsyncAgentex
from tests.utils import assert_matches_type
from agentex.types import (
    CheckpointPutResponse,
    CheckpointListResponse,
    CheckpointGetTupleResponse,
)

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestCheckpoints:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_list(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.list(
            thread_id="thread_id",
        )
        assert_matches_type(CheckpointListResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_list_with_all_params(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.list(
            thread_id="thread_id",
            before_checkpoint_id="before_checkpoint_id",
            checkpoint_ns="checkpoint_ns",
            filter_metadata={"foo": "bar"},
            limit=1,
        )
        assert_matches_type(CheckpointListResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_list(self, client: Agentex) -> None:
        response = client.checkpoints.with_raw_response.list(
            thread_id="thread_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = response.parse()
        assert_matches_type(CheckpointListResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_list(self, client: Agentex) -> None:
        with client.checkpoints.with_streaming_response.list(
            thread_id="thread_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = response.parse()
            assert_matches_type(CheckpointListResponse, checkpoint, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_delete_thread(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.delete_thread(
            thread_id="thread_id",
        )
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_delete_thread(self, client: Agentex) -> None:
        response = client.checkpoints.with_raw_response.delete_thread(
            thread_id="thread_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = response.parse()
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_delete_thread(self, client: Agentex) -> None:
        with client.checkpoints.with_streaming_response.delete_thread(
            thread_id="thread_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = response.parse()
            assert checkpoint is None

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_get_tuple(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.get_tuple(
            thread_id="thread_id",
        )
        assert_matches_type(Optional[CheckpointGetTupleResponse], checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_get_tuple_with_all_params(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.get_tuple(
            thread_id="thread_id",
            checkpoint_id="checkpoint_id",
            checkpoint_ns="checkpoint_ns",
        )
        assert_matches_type(Optional[CheckpointGetTupleResponse], checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_get_tuple(self, client: Agentex) -> None:
        response = client.checkpoints.with_raw_response.get_tuple(
            thread_id="thread_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = response.parse()
        assert_matches_type(Optional[CheckpointGetTupleResponse], checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_get_tuple(self, client: Agentex) -> None:
        with client.checkpoints.with_streaming_response.get_tuple(
            thread_id="thread_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = response.parse()
            assert_matches_type(Optional[CheckpointGetTupleResponse], checkpoint, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_put(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.put(
            checkpoint={"foo": "bar"},
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
        )
        assert_matches_type(CheckpointPutResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_put_with_all_params(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.put(
            checkpoint={"foo": "bar"},
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            blobs=[
                {
                    "channel": "channel",
                    "type": "type",
                    "version": "version",
                    "blob": "blob",
                }
            ],
            checkpoint_ns="checkpoint_ns",
            metadata={"foo": "bar"},
            parent_checkpoint_id="parent_checkpoint_id",
        )
        assert_matches_type(CheckpointPutResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_put(self, client: Agentex) -> None:
        response = client.checkpoints.with_raw_response.put(
            checkpoint={"foo": "bar"},
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = response.parse()
        assert_matches_type(CheckpointPutResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_put(self, client: Agentex) -> None:
        with client.checkpoints.with_streaming_response.put(
            checkpoint={"foo": "bar"},
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = response.parse()
            assert_matches_type(CheckpointPutResponse, checkpoint, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_put_writes(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.put_writes(
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            writes=[
                {
                    "blob": "blob",
                    "channel": "channel",
                    "idx": 0,
                    "task_id": "task_id",
                }
            ],
        )
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_put_writes_with_all_params(self, client: Agentex) -> None:
        checkpoint = client.checkpoints.put_writes(
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            writes=[
                {
                    "blob": "blob",
                    "channel": "channel",
                    "idx": 0,
                    "task_id": "task_id",
                    "task_path": "task_path",
                    "type": "type",
                }
            ],
            checkpoint_ns="checkpoint_ns",
            upsert=True,
        )
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_put_writes(self, client: Agentex) -> None:
        response = client.checkpoints.with_raw_response.put_writes(
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            writes=[
                {
                    "blob": "blob",
                    "channel": "channel",
                    "idx": 0,
                    "task_id": "task_id",
                }
            ],
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = response.parse()
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_put_writes(self, client: Agentex) -> None:
        with client.checkpoints.with_streaming_response.put_writes(
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            writes=[
                {
                    "blob": "blob",
                    "channel": "channel",
                    "idx": 0,
                    "task_id": "task_id",
                }
            ],
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = response.parse()
            assert checkpoint is None

        assert cast(Any, response.is_closed) is True


class TestAsyncCheckpoints:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_list(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.list(
            thread_id="thread_id",
        )
        assert_matches_type(CheckpointListResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_list_with_all_params(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.list(
            thread_id="thread_id",
            before_checkpoint_id="before_checkpoint_id",
            checkpoint_ns="checkpoint_ns",
            filter_metadata={"foo": "bar"},
            limit=1,
        )
        assert_matches_type(CheckpointListResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_list(self, async_client: AsyncAgentex) -> None:
        response = await async_client.checkpoints.with_raw_response.list(
            thread_id="thread_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = await response.parse()
        assert_matches_type(CheckpointListResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_list(self, async_client: AsyncAgentex) -> None:
        async with async_client.checkpoints.with_streaming_response.list(
            thread_id="thread_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = await response.parse()
            assert_matches_type(CheckpointListResponse, checkpoint, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_delete_thread(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.delete_thread(
            thread_id="thread_id",
        )
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_delete_thread(self, async_client: AsyncAgentex) -> None:
        response = await async_client.checkpoints.with_raw_response.delete_thread(
            thread_id="thread_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = await response.parse()
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_delete_thread(self, async_client: AsyncAgentex) -> None:
        async with async_client.checkpoints.with_streaming_response.delete_thread(
            thread_id="thread_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = await response.parse()
            assert checkpoint is None

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_get_tuple(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.get_tuple(
            thread_id="thread_id",
        )
        assert_matches_type(Optional[CheckpointGetTupleResponse], checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_get_tuple_with_all_params(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.get_tuple(
            thread_id="thread_id",
            checkpoint_id="checkpoint_id",
            checkpoint_ns="checkpoint_ns",
        )
        assert_matches_type(Optional[CheckpointGetTupleResponse], checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_get_tuple(self, async_client: AsyncAgentex) -> None:
        response = await async_client.checkpoints.with_raw_response.get_tuple(
            thread_id="thread_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = await response.parse()
        assert_matches_type(Optional[CheckpointGetTupleResponse], checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_get_tuple(self, async_client: AsyncAgentex) -> None:
        async with async_client.checkpoints.with_streaming_response.get_tuple(
            thread_id="thread_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = await response.parse()
            assert_matches_type(Optional[CheckpointGetTupleResponse], checkpoint, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_put(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.put(
            checkpoint={"foo": "bar"},
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
        )
        assert_matches_type(CheckpointPutResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_put_with_all_params(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.put(
            checkpoint={"foo": "bar"},
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            blobs=[
                {
                    "channel": "channel",
                    "type": "type",
                    "version": "version",
                    "blob": "blob",
                }
            ],
            checkpoint_ns="checkpoint_ns",
            metadata={"foo": "bar"},
            parent_checkpoint_id="parent_checkpoint_id",
        )
        assert_matches_type(CheckpointPutResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_put(self, async_client: AsyncAgentex) -> None:
        response = await async_client.checkpoints.with_raw_response.put(
            checkpoint={"foo": "bar"},
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = await response.parse()
        assert_matches_type(CheckpointPutResponse, checkpoint, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_put(self, async_client: AsyncAgentex) -> None:
        async with async_client.checkpoints.with_streaming_response.put(
            checkpoint={"foo": "bar"},
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = await response.parse()
            assert_matches_type(CheckpointPutResponse, checkpoint, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_put_writes(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.put_writes(
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            writes=[
                {
                    "blob": "blob",
                    "channel": "channel",
                    "idx": 0,
                    "task_id": "task_id",
                }
            ],
        )
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_put_writes_with_all_params(self, async_client: AsyncAgentex) -> None:
        checkpoint = await async_client.checkpoints.put_writes(
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            writes=[
                {
                    "blob": "blob",
                    "channel": "channel",
                    "idx": 0,
                    "task_id": "task_id",
                    "task_path": "task_path",
                    "type": "type",
                }
            ],
            checkpoint_ns="checkpoint_ns",
            upsert=True,
        )
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_put_writes(self, async_client: AsyncAgentex) -> None:
        response = await async_client.checkpoints.with_raw_response.put_writes(
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            writes=[
                {
                    "blob": "blob",
                    "channel": "channel",
                    "idx": 0,
                    "task_id": "task_id",
                }
            ],
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        checkpoint = await response.parse()
        assert checkpoint is None

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_put_writes(self, async_client: AsyncAgentex) -> None:
        async with async_client.checkpoints.with_streaming_response.put_writes(
            checkpoint_id="checkpoint_id",
            thread_id="thread_id",
            writes=[
                {
                    "blob": "blob",
                    "channel": "channel",
                    "idx": 0,
                    "task_id": "task_id",
                }
            ],
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            checkpoint = await response.parse()
            assert checkpoint is None

        assert cast(Any, response.is_closed) is True
