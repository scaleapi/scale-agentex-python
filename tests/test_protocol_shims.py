"""Tests that pin the back-compat contract for protocol-type shims.

The canonical location for wire-protocol shapes is :mod:`agentex.protocol`
(see PR scaleapi/scale-agentex-python#371). The historical locations
:mod:`agentex.lib.types.acp` and :mod:`agentex.lib.types.json_rpc` are
preserved as re-export shims so external consumers' existing imports
continue to work.

These tests enforce two invariants:

1. **Symbol parity** — every public name the original modules exported
   is still importable from the old path. Greptile flagged
   ``RPC_SYNC_METHODS`` and ``PARAMS_MODEL_BY_METHOD`` as missing in an
   earlier pass; this test prevents that regression.
2. **Identity** — the class objects at the shim path are the *same*
   objects as the canonical path. Without this, type-narrowing via
   ``isinstance`` or pattern matching would silently misbehave for code
   that mixes import styles.

Also asserts the :class:`pydantic.ConfigDict` settings on the JSON-RPC
classes survived the move from :mod:`agentex.lib.utils.model_utils` to
plain :mod:`pydantic` — Greptile flagged the silent loss of
``from_attributes=True`` / ``populate_by_name=True``.
"""

from __future__ import annotations


def test_acp_shim_re_exports_all_original_symbols() -> None:
    """Every name historically exported from agentex.lib.types.acp must
    still be importable from that path via the back-compat shim."""
    # Importing each symbol; ImportError here means the shim regressed.
    from agentex.lib.types.acp import (  # noqa: F401
        PARAMS_MODEL_BY_METHOD,
        RPC_SYNC_METHODS,
        CancelTaskParams,
        CreateTaskParams,
        RPCMethod,
        SendEventParams,
        SendMessageParams,
    )


def test_json_rpc_shim_re_exports_all_original_symbols() -> None:
    """Every name historically exported from agentex.lib.types.json_rpc
    must still be importable from that path via the back-compat shim."""
    from agentex.lib.types.json_rpc import (  # noqa: F401
        JSONRPCError,
        JSONRPCRequest,
        JSONRPCResponse,
    )


def test_acp_shim_classes_are_identical_to_canonical() -> None:
    """Shim re-exports must be the *same* class objects as the canonical
    path. Different objects would break ``isinstance`` for code that
    mixes import styles."""
    from agentex.lib.types import acp as shim
    from agentex.protocol import acp as canon

    assert shim.RPCMethod is canon.RPCMethod
    assert shim.CreateTaskParams is canon.CreateTaskParams
    assert shim.SendMessageParams is canon.SendMessageParams
    assert shim.SendEventParams is canon.SendEventParams
    assert shim.CancelTaskParams is canon.CancelTaskParams
    assert shim.RPC_SYNC_METHODS is canon.RPC_SYNC_METHODS
    assert shim.PARAMS_MODEL_BY_METHOD is canon.PARAMS_MODEL_BY_METHOD


def test_json_rpc_shim_classes_are_identical_to_canonical() -> None:
    """Same identity check for the JSON-RPC envelope types."""
    from agentex.lib.types import json_rpc as shim
    from agentex.protocol import json_rpc as canon

    assert shim.JSONRPCError is canon.JSONRPCError
    assert shim.JSONRPCRequest is canon.JSONRPCRequest
    assert shim.JSONRPCResponse is canon.JSONRPCResponse


def test_json_rpc_classes_preserve_legacy_model_config() -> None:
    """Pre-refactor, JSON-RPC classes inherited
    ``from_attributes=True`` / ``populate_by_name=True`` from
    ``agentex.lib.utils.model_utils.BaseModel``. The refactor swapped
    to plain ``pydantic.BaseModel`` and set ``model_config`` explicitly
    to preserve both flags. Catch any future drop."""
    from agentex.protocol.json_rpc import (
        JSONRPCError,
        JSONRPCRequest,
        JSONRPCResponse,
    )

    for cls in (JSONRPCError, JSONRPCRequest, JSONRPCResponse):
        assert cls.model_config.get("from_attributes") is True, (
            f"{cls.__name__}.model_config dropped from_attributes=True"
        )
        assert cls.model_config.get("populate_by_name") is True, (
            f"{cls.__name__}.model_config dropped populate_by_name=True"
        )
