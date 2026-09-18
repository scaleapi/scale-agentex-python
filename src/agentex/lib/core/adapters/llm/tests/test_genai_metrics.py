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
from agentex.lib.core.adapters.llm._genai_metrics import (
    _split_model,
    resolve_model,
    inference_call,
)


@pytest.fixture(autouse=True)
def _forget_resolved_sgp_obs():
    """Clear the resolved-once module handle around every test.

    It is process-wide state, so without this the first test to run with sgp-obs
    absent would cache None for the rest of the session and every later test that
    injects a fake ``sgp_obs.metrics`` would silently exercise the null path instead
    of the one it means to.
    """
    _genai_metrics._reset_for_tests()
    yield
    _genai_metrics._reset_for_tests()


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
            # A bare name litellm cannot place is OpenAI per its own default, and
            # reaches OpenAI through the openai client — the instrumentor sees it.
            ("gpt-4o", "openai", True),
            ("openai/gpt-4o", "openai", True),
            # Azure is served by openai.AzureOpenAI, so the client instrumentor
            # records it and we must NOT. Reading the prefix called this native.
            ("azure/gpt-4o", "azure", True),
            # Every openai-compatible provider litellm supports has the same shape:
            # a vendor prefix, but dispatched over the openai client.
            ("groq/llama3-8b-8192", "groq", True),
            ("deepseek/deepseek-chat", "deepseek", True),
            # A bare Anthropic model is legal and routes NATIVELY to Anthropic, so
            # nothing else records it. The prefix reader called this OpenAI and
            # stood down for an instrumentor that never saw the call.
            ("claude-sonnet-4-20250514", "anthropic", False),
            # Genuinely native: no openai client anywhere in the path.
            ("gemini/gemini-2.0-flash", "gemini", False),
        ],
    )
    def test_vendor_and_transport(self, model, vendor, over_openai_client):
        assert _split_model(model) == (vendor, over_openai_client)

    def test_an_unresolvable_model_falls_back_to_the_prefix(self):
        """litellm raises for a model it cannot place (measured:
        claude-3-5-sonnet-latest). That call will fail in litellm too, but the lookup
        must not raise on the way there."""
        assert _split_model("claude-3-5-sonnet-latest") == ("openai", True)
        assert _split_model("madeup_vendor/some-model") == ("madeup_vendor", False)

    def test_empty_model_does_not_raise(self):
        """kwargs.get("model") is "" when a caller passes model positionally.
        Falling back to litellm's own default is right, and must not blow up."""
        assert _split_model("") == ("openai", True)


class TestTheRoutingDecisionComesFromLitellm:
    """The boolean decides whether `call()` stands down for the OpenAI client
    instrumentor or records itself, so getting it wrong either double-counts a call or
    loses it entirely. Both happened while it was read off the model prefix."""

    def test_azure_is_not_double_counted(self):
        """litellm serves azure/* with openai.AzureOpenAI (litellm/main.py,
        `if custom_llm_provider == "azure"`), so the client instrumentor already
        records it. Recording here as well counted every Azure call twice."""
        _provider, over_openai_client = _split_model("azure/gpt-4o")
        assert over_openai_client is True

    def test_a_bare_anthropic_model_is_recorded(self):
        """The opposite failure: nothing else sees this call, so standing down meant
        it went unmeasured and nothing said so."""
        provider, over_openai_client = _split_model("claude-sonnet-4-20250514")
        assert provider == "anthropic"
        assert over_openai_client is False

    def test_the_proxy_vendor_survives_resolution(self):
        """The reason this module exists at all: from inside the OpenAI client a
        proxied call is just "openai". The prefix is stripped before resolving so the
        vendor underneath is still the label."""
        assert _split_model("litellm_proxy/anthropic/claude-sonnet-4") == (
            "anthropic",
            True,
        )

    def test_the_provider_list_agrees_with_litellm(self):
        """Pinned to litellm's own list rather than a copy of it, because the copy
        would go stale every release."""
        import litellm

        from agentex.lib.core.adapters.llm._genai_metrics import _over_openai_client

        for provider in list(getattr(litellm, "openai_compatible_providers", []))[:20]:
            assert _over_openai_client(provider), provider
        for provider in ("anthropic", "bedrock", "vertex_ai", "gemini"):
            assert not _over_openai_client(provider), provider

    def test_losing_litellms_list_is_not_silent(self, monkeypatch, caplog):
        """`openai_compatible_providers` is not in litellm's __all__, so it is read
        defensively. But degrading quietly would re-introduce the double counting this
        whole function exists to prevent, so the fallback has to be audible."""
        import litellm

        monkeypatch.delattr(litellm, "openai_compatible_providers", raising=False)
        _genai_metrics._reset_for_tests()

        with caplog.at_level("WARNING", logger=_genai_metrics.logger.name):
            # The five explicit ones still work; the ~50 from litellm no longer do.
            assert _genai_metrics._over_openai_client("azure") is True
            assert _genai_metrics._over_openai_client("groq") is False
        assert any("openai_compatible_providers" in r.message for r in caplog.records), [
            r.message for r in caplog.records
        ]

    def test_an_unresolvable_model_does_not_spam_stdout(self):
        """litellm prints a red "Provider List" banner to STDOUT (not logging, so it
        cannot be filtered) every time resolution fails. Uncached, an agent on a model
        string litellm cannot place printed it on every single call."""
        import io
        import contextlib

        _genai_metrics._reset_for_tests()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for _ in range(25):
                _split_model("claude-3-5-sonnet-latest")
        assert buf.getvalue().count("Provider List") <= 1, buf.getvalue()[:400]


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
        # Resolution is cached, so drop anything a previous call resolved -- otherwise
        # hiding the module here would have no effect.
        _genai_metrics._reset_for_tests()

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


class TestTheImportIsResolvedOnce:
    """Python does not cache a FAILED import, so importing inside ``inference_call``
    re-walked sys.path on every model call. Measured at 62us per attempt with five
    sys.path entries, which was most of the gateway's per-call overhead for the
    majority of agents -- the ones with no sgp-obs installed."""

    def test_a_missing_sgp_obs_is_looked_up_once_not_per_call(self, monkeypatch):
        attempts = []
        real_import = builtins.__import__

        def counting_import(name, *args, **kwargs):
            if name == "sgp_obs" or name.startswith("sgp_obs."):
                attempts.append(name)
                raise ImportError("No module named 'sgp_obs'")
            return real_import(name, *args, **kwargs)

        for name in [m for m in sys.modules if m.startswith("sgp_obs")]:
            monkeypatch.delitem(sys.modules, name, raising=False)
        monkeypatch.setattr(builtins, "__import__", counting_import)

        for _ in range(50):
            assert inference_call({"model": "gpt-4o"}) is _genai_metrics._NULL_CALL

        assert len(attempts) == 1, f"expected one import attempt, got {len(attempts)}"

    def test_a_present_sgp_obs_is_looked_up_once_too(self, monkeypatch):
        """The handle must cache the module as well as the failure, or an agent that
        DOES have sgp-obs keeps paying for a lookup it already did."""
        attempts = []

        class _Genai:
            CHAT = "chat"
            OPENAI_SPEC = "openai"
            OPENAI = "openai"

            @staticmethod
            def call(**_kwargs):
                return _genai_metrics._NULL_CALL

        module = type(sys)("sgp_obs.metrics")
        module.genai = _Genai
        monkeypatch.setitem(sys.modules, "sgp_obs", type(sys)("sgp_obs"))
        monkeypatch.setitem(sys.modules, "sgp_obs.metrics", module)

        real_import = builtins.__import__

        def counting_import(name, *args, **kwargs):
            if name == "sgp_obs" or name.startswith("sgp_obs."):
                attempts.append(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", counting_import)

        for _ in range(50):
            inference_call({"model": "gpt-4o"})

        assert len(attempts) == 1, f"expected one import attempt, got {len(attempts)}"

    def test_the_recorder_is_still_the_real_one_after_caching(self, monkeypatch):
        """Caching must not turn a working sgp-obs into the null path on call two."""
        seen = []

        class _Genai:
            CHAT = "chat"
            OPENAI_SPEC = "openai"
            OPENAI = "openai"

            @staticmethod
            def call(**kwargs):
                seen.append(kwargs["model"])
                return _genai_metrics._NULL_CALL

        module = type(sys)("sgp_obs.metrics")
        module.genai = _Genai
        monkeypatch.setitem(sys.modules, "sgp_obs", type(sys)("sgp_obs"))
        monkeypatch.setitem(sys.modules, "sgp_obs.metrics", module)

        for index in range(3):
            inference_call({"model": f"anthropic/claude-{index}"})

        assert seen == ["anthropic/claude-0", "anthropic/claude-1", "anthropic/claude-2"]


class TestResolveModel:
    """litellm takes `model` as its FIRST positional argument and the gateway forwards
    *args untouched, so a positional call is legal and must still be measured.

    Reading only kwargs does not merely mislabel the vendor: an empty model resolves to
    the default vendor "openai", which sets transport=OPENAI, which makes call() stand
    down for the OpenAI client instrumentor — while litellm routes natively to Anthropic
    and never touches that client. Nothing records it and nothing says so.
    """

    def test_keyword_model(self):
        assert resolve_model((), {"model": "gpt-4o"}) == "gpt-4o"

    def test_positional_model(self):
        assert resolve_model(("anthropic/claude-sonnet-4",), {}) == "anthropic/claude-sonnet-4"

    def test_keyword_wins_over_positional(self):
        """litellm itself would reject both, but if it ever resolved one, the keyword is
        the explicit intent."""
        assert resolve_model(("a/b",), {"model": "c/d"}) == "c/d"

    def test_no_model_at_all(self):
        assert resolve_model((), {}) == ""

    def test_a_non_string_first_arg_is_not_a_model(self):
        """*args is forwarded verbatim, so args[0] is whatever the caller passed."""
        assert resolve_model(([{"role": "user"}],), {}) == ""

    def test_positional_native_vendor_does_not_stand_down(self, monkeypatch):
        """The regression this guards: a positional Anthropic model must be recorded by
        the gateway, because nothing else will."""
        seen = {}

        class _Genai:
            CHAT = "chat"
            OPENAI_SPEC = "openai"
            OPENAI = "openai"

            @staticmethod
            def call(**kwargs):
                seen.update(kwargs)
                return _genai_metrics._NULL_CALL

        module = type(sys)("sgp_obs.metrics")
        module.genai = _Genai
        monkeypatch.setitem(sys.modules, "sgp_obs", type(sys)("sgp_obs"))
        monkeypatch.setitem(sys.modules, "sgp_obs.metrics", module)

        inference_call({}, ("anthropic/claude-sonnet-4",))
        assert seen["model"] == "anthropic/claude-sonnet-4"
        assert seen["provider"] == "anthropic"
        # Empty transport == "no OpenAI-client overlap, so record it here".
        assert seen["transport"] == ""
