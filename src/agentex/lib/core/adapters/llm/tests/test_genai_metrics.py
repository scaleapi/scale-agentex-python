"""Tests for ``agentex.lib.core.adapters.llm._genai_metrics``.

The important property is the one that holds in every environment today: with
``sgp-obs`` absent, :func:`inference_call` must hand back something the litellm
gateway can drive as an async context manager, whose ``observe()`` returns the
response untouched and which never swallows the caller's exception. That is the
path every agent without the ``obs`` extra takes on every model call, so a
regression here breaks model calls rather than just losing a metric.
"""

from __future__ import annotations

import sys
import builtins

import pytest

from agentex.lib.core.adapters.llm import _genai_metrics
from agentex.lib.core.adapters.llm._genai_metrics import _split_model, inference_call


class TestSplitModel:
    """``(vendor, goes_out_over_the_openai_client)``. The boolean decides whether
    ``call()`` stands down for the OpenAI client instrumentor or records itself, so
    getting it wrong either double-counts a call or loses it."""

    @pytest.mark.parametrize(
        ("model", "vendor", "over_openai_client"),
        [
            # Proxy mode: litellm sends this to an OpenAI-compatible proxy over the
            # openai client, but the caller asked for a non-OpenAI vendor.
            ("litellm_proxy/anthropic/claude-sonnet-4", "anthropic", True),
            ("litellm_proxy/gpt-4o", "openai", True),
            # Native routing: litellm's own handler, no openai client involved.
            ("anthropic/claude-sonnet-4", "anthropic", False),
            ("bedrock/anthropic.claude-v2", "bedrock", False),
            ("vertex_ai/gemini-2.0-flash", "vertex_ai", False),
            # A bare name is OpenAI per litellm's default, and reaches OpenAI
            # through the openai client — so the instrumentor already sees it.
            ("gpt-4o", "openai", True),
            ("openai/gpt-4o", "openai", True),
        ],
    )
    def test_vendor_and_transport(self, model, vendor, over_openai_client):
        assert _split_model(model) == (vendor, over_openai_client)

    def test_empty_model_does_not_raise(self):
        """kwargs.get("model") is "" when a caller passes model positionally.
        Falling back to litellm's own default is right, and must not blow up."""
        assert _split_model("") == ("openai", True)


class TestFailsOpenWithoutSgpObs:
    @staticmethod
    def _hide_sgp_obs(monkeypatch):
        for name in [m for m in sys.modules if m.startswith("sgp_obs")]:
            monkeypatch.delitem(sys.modules, name, raising=False)
        real_import = builtins.__import__

        def no_sgp_obs(name, *args, **kwargs):
            if name == "sgp_obs" or name.startswith("sgp_obs."):
                raise ImportError("No module named 'sgp_obs'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_sgp_obs)
        # The "already warned" latch is module state; reset so the path is exercised.
        monkeypatch.setattr(_genai_metrics, "_warned", False)

    def test_returns_a_usable_recorder_not_none(self, monkeypatch):
        self._hide_sgp_obs(monkeypatch)
        assert inference_call({"model": "gpt-4o"}) is _genai_metrics._NULL_CALL

    async def test_observe_returns_the_response_unchanged(self, monkeypatch):
        """The gateway does `call.observe(await acompletion(...))`, so an observe()
        that returned None would turn every completion into None."""
        self._hide_sgp_obs(monkeypatch)
        sentinel = object()
        async with inference_call({"model": "gpt-4o"}) as call:
            assert call.observe(sentinel) is sentinel

    async def test_does_not_suppress_the_callers_exception(self, monkeypatch):
        """__aexit__ must return falsey. Suppressing here would make a failed model
        call look like a successful one that returned nothing."""
        self._hide_sgp_obs(monkeypatch)
        with pytest.raises(ValueError, match="upstream"):
            async with inference_call({"model": "gpt-4o"}):
                raise ValueError("upstream blew up")

    async def test_cancellation_still_propagates(self, monkeypatch):
        """CancelledError is a BaseException; the `async with` in the gateway exists
        so a disappearing caller is not silently dropped."""
        import asyncio

        self._hide_sgp_obs(monkeypatch)
        with pytest.raises(asyncio.CancelledError):
            async with inference_call({"model": "gpt-4o"}):
                raise asyncio.CancelledError()

    def test_a_broken_sgp_obs_does_not_break_a_model_call(self, monkeypatch):
        """Not just ImportError: anything raised while starting a record must fall
        back to the null recorder."""
        module = type(sys)("sgp_obs.metrics")
        genai = type(sys)("genai")

        def exploding(**_kwargs):
            raise RuntimeError("sgp-obs internals changed")

        genai.call = exploding
        genai.CHAT = "chat"
        genai.OPENAI_SPEC = "openai"
        genai.OPENAI = "openai"
        module.genai = genai
        monkeypatch.setitem(sys.modules, "sgp_obs", type(sys)("sgp_obs"))
        monkeypatch.setitem(sys.modules, "sgp_obs.metrics", module)
        assert inference_call({"model": "gpt-4o"}) is _genai_metrics._NULL_CALL
