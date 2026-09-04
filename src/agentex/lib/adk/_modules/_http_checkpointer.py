"""HTTP-proxy LangGraph checkpointer.

Proxies all checkpoint operations through the agentex backend API
instead of connecting directly to PostgreSQL. The backend handles DB
operations through its own connection pool.
"""

from __future__ import annotations

import base64
import random
from typing import Any, cast, override
from collections.abc import Iterator, Sequence, AsyncIterator

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    Checkpoint,
    ChannelVersions,
    CheckpointTuple,
    CheckpointMetadata,
    BaseCheckpointSaver,
    get_checkpoint_id,
    get_serializable_checkpoint_metadata,
)
from langgraph.checkpoint.serde.types import TASKS

from agentex import AsyncAgentex
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


def _bytes_to_b64(data: bytes | None) -> str | None:
    if data is None:
        return None
    return base64.b64encode(data).decode("ascii")


def _b64_to_bytes(data: str | None) -> bytes | None:
    if data is None:
        return None
    return base64.b64decode(data)


class HttpCheckpointSaver(BaseCheckpointSaver[str]):
    """Checkpoint saver that proxies operations through the agentex HTTP API."""

    def __init__(self, client: AsyncAgentex) -> None:
        super().__init__()
        self._http = client._client  # noqa: SLF001  # raw httpx.AsyncClient for direct HTTP calls

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        """POST JSON to the backend and return parsed response."""
        response = await self._http.post(
            f"/checkpoints{path}",
            json=body,
        )
        response.raise_for_status()
        # put-writes and delete-thread return 204 No Content (no JSON body)
        if response.status_code == 204:
            return None
        return response.json()

    # ── get_next_version (same as BasePostgresSaver) ──

    @override
    def get_next_version(self, current: str | None, channel: None) -> str:  # type: ignore[override]  # noqa: ARG002
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])
        next_v = current_v + 1
        next_h = random.random()  # noqa: S311
        return f"{next_v:032}.{next_h:016}"

    # ── async interface ──

    @override
    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        configurable = config["configurable"]  # type: ignore[reportTypedDictNotRequiredAccess]
        thread_id = configurable["thread_id"]
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        data = await self._post(
            "/get-tuple",
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            },
        )

        if data is None:
            return None

        # Reconstruct channel_values from blobs + inline values
        checkpoint = data["checkpoint"]
        channel_values: dict[str, Any] = {}

        # Inline primitive values already in the checkpoint
        if "channel_values" in checkpoint and checkpoint["channel_values"]:
            channel_values.update(checkpoint["channel_values"])

        # Deserialize blobs
        for blob in data.get("blobs", []):
            blob_type = blob["type"]
            if blob_type == "empty":
                continue
            blob_bytes = _b64_to_bytes(blob.get("blob"))
            channel_values[blob["channel"]] = self.serde.loads_typed((blob_type, blob_bytes))

        checkpoint["channel_values"] = channel_values

        # Handle pending_sends migration for v < 4
        if checkpoint.get("v", 0) < 4 and data.get("parent_checkpoint_id"):
            # The backend already returns all writes; filter for TASKS channel sends
            pending_sends_raw = [w for w in data.get("pending_writes", []) if w["channel"] == TASKS]
            if pending_sends_raw:
                sends = [
                    self.serde.loads_typed((w["type"], _b64_to_bytes(w["blob"])))
                    for w in pending_sends_raw
                    if w.get("type")
                ]
                if sends:
                    enc, blob_data = self.serde.dumps_typed(sends)
                    channel_values[TASKS] = self.serde.loads_typed((enc, blob_data))
                    if checkpoint.get("channel_versions") is None:
                        checkpoint["channel_versions"] = {}
                    checkpoint["channel_versions"][TASKS] = (
                        max(checkpoint["channel_versions"].values())
                        if checkpoint["channel_versions"]
                        else self.get_next_version(None, None)
                    )

        # Reconstruct pending writes
        pending_writes: list[tuple[str, str, Any]] = []
        for w in data.get("pending_writes", []):
            w_type = w.get("type")
            w_bytes = _b64_to_bytes(w.get("blob"))
            pending_writes.append(
                (
                    w["task_id"],
                    w["channel"],
                    self.serde.loads_typed((w_type, w_bytes)) if w_type else w_bytes,
                )
            )

        parent_config: RunnableConfig | None = None
        if data.get("parent_checkpoint_id"):
            parent_config = {
                "configurable": {
                    "thread_id": data["thread_id"],
                    "checkpoint_ns": data["checkpoint_ns"],
                    "checkpoint_id": data["parent_checkpoint_id"],
                }
            }

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": data["thread_id"],
                    "checkpoint_ns": data["checkpoint_ns"],
                    "checkpoint_id": data["checkpoint_id"],
                }
            },
            checkpoint=checkpoint,
            metadata=data["metadata"],
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    @override
    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        configurable = config["configurable"].copy()  # type: ignore[reportTypedDictNotRequiredAccess]
        thread_id = configurable.pop("thread_id")
        checkpoint_ns = configurable.pop("checkpoint_ns")
        checkpoint_id = configurable.pop("checkpoint_id", None)

        # Separate inline values from blobs (same logic as AsyncPostgresSaver)
        copy = checkpoint.copy()
        copy["channel_values"] = copy["channel_values"].copy()
        blob_values: dict[str, Any] = {}
        for k, v in checkpoint["channel_values"].items():
            if v is None or isinstance(v, (str, int, float, bool)):
                pass
            else:
                blob_values[k] = copy["channel_values"].pop(k)

        # Serialize blob values
        blobs: list[dict[str, Any]] = []
        for k, ver in new_versions.items():
            if k in blob_values:
                enc, data = self.serde.dumps_typed(blob_values[k])
                blobs.append(
                    {
                        "channel": k,
                        "version": cast(str, ver),
                        "type": enc,
                        "blob": _bytes_to_b64(data),
                    }
                )
            else:
                blobs.append(
                    {
                        "channel": k,
                        "version": cast(str, ver),
                        "type": "empty",
                        "blob": None,
                    }
                )

        await self._post(
            "/put",
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
                "parent_checkpoint_id": checkpoint_id,
                "checkpoint": copy,
                "metadata": get_serializable_checkpoint_metadata(config, metadata),
                "blobs": blobs,
            },
        )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    @override
    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        configurable = config["configurable"]  # type: ignore[reportTypedDictNotRequiredAccess]
        thread_id = configurable["thread_id"]
        checkpoint_ns = configurable["checkpoint_ns"]
        checkpoint_id = configurable["checkpoint_id"]

        upsert = all(w[0] in WRITES_IDX_MAP for w in writes)

        serialized_writes: list[dict[str, Any]] = []
        for idx, (channel, value) in enumerate(writes):
            enc, data = self.serde.dumps_typed(value)
            serialized_writes.append(
                {
                    "task_id": task_id,
                    "idx": WRITES_IDX_MAP.get(channel, idx),
                    "channel": channel,
                    "type": enc,
                    "blob": _bytes_to_b64(data),
                    "task_path": task_path,
                }
            )

        await self._post(
            "/put-writes",
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "writes": serialized_writes,
                "upsert": upsert,
            },
        )

    @override
    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        body: dict[str, Any] = {}
        if config:
            configurable = config["configurable"]  # type: ignore[reportTypedDictNotRequiredAccess]
            body["thread_id"] = configurable["thread_id"]
            checkpoint_ns = configurable.get("checkpoint_ns")
            if checkpoint_ns is not None:
                body["checkpoint_ns"] = checkpoint_ns
        if filter:
            body["filter_metadata"] = filter
        if before:
            body["before_checkpoint_id"] = get_checkpoint_id(before)
        if limit is not None:
            body["limit"] = limit

        results = await self._post("/list", body)

        for item in results or []:
            # For each listed checkpoint, reconstruct a CheckpointTuple
            # with inline channel_values only (blobs not included in list)
            checkpoint = item["checkpoint"]
            parent_config: RunnableConfig | None = None
            if item.get("parent_checkpoint_id"):
                parent_config = {
                    "configurable": {
                        "thread_id": item["thread_id"],
                        "checkpoint_ns": item["checkpoint_ns"],
                        "checkpoint_id": item["parent_checkpoint_id"],
                    }
                }
            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": item["thread_id"],
                        "checkpoint_ns": item["checkpoint_ns"],
                        "checkpoint_id": item["checkpoint_id"],
                    }
                },
                checkpoint=checkpoint,
                metadata=item["metadata"],
                parent_config=parent_config,
                pending_writes=None,
            )

    @override
    async def adelete_thread(self, thread_id: str) -> None:
        await self._post("/delete-thread", {"thread_id": thread_id})

    # ── sync stubs (required by BaseCheckpointSaver) ──
    # LangGraph always calls the async methods (aget_tuple, aput, etc.).
    # Sync methods are only required by the abstract base class.

    @override
    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        raise NotImplementedError("Use aget_tuple() instead.")

    @override
    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        raise NotImplementedError("Use alist() instead.")

    @override
    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        raise NotImplementedError("Use aput() instead.")

    @override
    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        raise NotImplementedError("Use aput_writes() instead.")

    @override
    def delete_thread(self, thread_id: str) -> None:
        raise NotImplementedError("Use adelete_thread() instead.")
