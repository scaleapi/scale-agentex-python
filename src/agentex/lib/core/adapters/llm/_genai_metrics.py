"""GenAI metrics for the litellm gateway, via ``sgp_obs.metrics.genai.call()``.

Why the SDK does this rather than leaving it to zero-code instrumentation:

Most model calls in the fleet reach the wire through the ``openai`` client, and for
those, patching that one client covers everything with no code — ``Runner.run``, the
ADK's openai provider, and litellm pointed at an OpenAI-compatible proxy. The client
patch cannot help in two situations, and this gateway hits both:

1. **litellm routing natively** to Anthropic, Bedrock, Vertex or Azure never touches
   the ``openai`` client, so nothing records it at all.
2. Even in proxy mode, the patch sits *inside* the OpenAI client, so it reports
   ``gen_ai.provider.name="openai"`` — the protocol. It cannot know that the caller
   asked for ``claude-sonnet-4``. This gateway chose the vendor, so it can say so.

``transport=`` resolves the overlap between the two: when the call is going out over
the OpenAI client, we name that, and ``call()`` stands down if the client instrumentor
is already recording. When litellm routes natively there is no such overlap, so we
record. That decision is made per call, from the model string, in
:func:`_split_model`.

Everything here is fail-open: sgp-obs is an optional dependency and a telemetry problem
must never fail a model call. If the import fails, :func:`inference_call` returns an
object that records nothing, and the failure is remembered so that later calls cost an
identity check rather than another walk of sys.path.
"""

from __future__ import annotations

from typing import Any

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# litellm's directive for "send this to the configured OpenAI-compatible proxy". It is
# a routing instruction, not a vendor, so it is stripped before reading the vendor.
_PROXY_PREFIX = "litellm_proxy/"

# A bare model name with no "<vendor>/" prefix is OpenAI, per litellm's own default.
_DEFAULT_VENDOR = "openai"

# Providers litellm dispatches through the `openai` Python client, and which the OpenAI
# client instrumentor therefore already records, but which litellm does NOT carry in
# `openai_compatible_providers`. Azure is the one that matters: it is served by
# openai.AzureOpenAI (litellm/main.py, `if custom_llm_provider == "azure"`), so reading
# the prefix alone and calling it a native vendor double-counted every Azure call.
_EXTRA_OPENAI_CLIENT_PROVIDERS = frozenset(
    {"openai", "azure", "azure_text", "text-completion-openai", "custom_openai"}
)

_OPENAI_CLIENT_PROVIDERS_UNRESOLVED = object()
_openai_client_providers: Any = _OPENAI_CLIENT_PROVIDERS_UNRESOLVED


def _over_openai_client(provider: str) -> bool:
    """Would the OpenAI client instrumentor already have recorded this call?

    Answered from litellm's own ``openai_compatible_providers`` rather than a list of
    our own, because that list is what litellm actually routes on and it grows every
    release (54 entries as of 1.87.0: groq, deepseek, xai, fireworks_ai, ...).
    """
    global _openai_client_providers
    if _openai_client_providers is _OPENAI_CLIENT_PROVIDERS_UNRESOLVED:
        compatible: Any = None
        try:
            import litellm

            # Read via getattr: the attribute is not in litellm's __all__, so it is
            # not a promised export and a future release may rename or drop it.
            compatible = getattr(litellm, "openai_compatible_providers", None)
        except Exception:  # pragma: no cover - litellm is a hard dependency
            compatible = None

        if compatible:
            _openai_client_providers = (
                frozenset(compatible) | _EXTRA_OPENAI_CLIENT_PROVIDERS
            )
        else:
            # Degrading quietly here would re-introduce the double counting this
            # function exists to prevent: every openai-compatible provider would look
            # native again and be recorded twice. Say so rather than drift.
            logger.warning(
                "litellm no longer exposes openai_compatible_providers, so GenAI "
                "metrics can only recognise %d providers as reaching the model over "
                "the OpenAI client. Calls to openai-compatible providers such as "
                "groq or deepseek may now be counted twice, once here and once by "
                "the OpenAI client instrumentor.",
                len(_EXTRA_OPENAI_CLIENT_PROVIDERS),
            )
            _openai_client_providers = _EXTRA_OPENAI_CLIENT_PROVIDERS
    return provider in _openai_client_providers

# sgp-obs is an optional install (see ``sgp_obs_setup``), and Python does NOT cache a
# FAILED import, so importing inside ``inference_call`` re-walked sys.path on every
# single model call for the majority of agents that do not have it. Measured on
# 0.27.0b2 in a venv with five sys.path entries (a container image has more): 62us per
# attempt, which took the gateway's own per-call overhead from 12us to 84us. Resolved
# once, to the module or to None -- the shape ``base_acp_server`` already uses for
# ``sgp_obs.context``, for the same reason.
_GENAI_UNRESOLVED = object()
_genai_module: Any = _GENAI_UNRESOLVED


def _genai() -> Any | None:
    """The sgp-obs GenAI metrics module, or None when it is not installed.

    Resolved on first use rather than at import time, so that importing the litellm
    adapter does not pay for it and the answer is read after startup has run.

    The debug line is here rather than at the call site because this body runs exactly
    once, which is the only place a "said it once" latch is not needed.
    """
    global _genai_module
    if _genai_module is _GENAI_UNRESOLVED:
        try:
            # See sgp_obs_setup.py: optional, not publicly installable, absent in CI.
            from sgp_obs.metrics import genai  # type: ignore[import-not-found]

            _genai_module = genai
        except Exception:
            _genai_module = None
            logger.debug(
                "sgp-obs is not available; GenAI metrics are off for litellm calls"
            )
    return _genai_module


def _split_model(model: str) -> tuple[str, bool]:
    """``(provider, goes_out_over_the_openai_client)`` for a litellm model string.

    ``"litellm_proxy/anthropic/claude-sonnet-4"`` -> ``("anthropic", True)``
    ``"anthropic/claude-sonnet-4"``              -> ``("anthropic", False)``
    ``"claude-sonnet-4-20250514"``               -> ``("anthropic", False)``
    ``"azure/gpt-4o"``                           -> ``("azure", True)``
    ``"gpt-4o"``                                 -> ``("openai", True)``

    The provider comes from ``litellm.get_llm_provider`` — the same resolution litellm
    uses to route the call — rather than from reading the prefix. Reading the prefix got
    two whole classes of call wrong, in opposite directions:

    * **Prefixed but still over the OpenAI client.** ``azure/gpt-4o`` looks like a
      native vendor, but litellm serves it with ``openai.AzureOpenAI``, so the client
      instrumentor recorded it too and this recorded it a second time. The same held
      for every openai-compatible provider litellm supports — groq, deepseek, xai,
      fireworks_ai and ~50 others — all of which look "native" to a prefix reader.
    * **Unprefixed but NOT OpenAI.** ``claude-sonnet-4-20250514`` is a legal litellm
      model string that routes to Anthropic, but a bare name was assumed to be OpenAI,
      so this stood down for an instrumentor that never saw the call. Nothing recorded
      it and nothing said so.

    The proxy prefix is stripped before resolving, deliberately: ``litellm_proxy/`` is a
    routing instruction, so the vendor underneath it is the interesting label — and the
    one thing the OpenAI client instrumentor cannot report, since from inside that
    client the call is simply "openai".
    """
    proxied = model.startswith(_PROXY_PREFIX)
    rest = model[len(_PROXY_PREFIX):] if proxied else model

    provider = _resolve_provider(rest)
    if provider is None:
        # litellm could not resolve it, which means it would not route the call either.
        # Fall back to the prefix so an exotic string still gets a sensible label.
        provider = rest.split("/", 1)[0] if "/" in rest else _DEFAULT_VENDOR
        provider = provider or _DEFAULT_VENDOR

    # Proxy mode always leaves over the OpenAI client, whatever the vendor underneath.
    return provider, proxied or _over_openai_client(provider)


# Resolved providers, keyed by model string. A plain dict rather than lru_cache:
# `functools.lru_cache` is banned in this repo (TID251) and the sanctioned replacement
# lives in `agentex._utils`, which is the generated client half that `agentex/lib` does
# not otherwise import from. This module already keeps two other resolve-once caches,
# so a third is the least surprising option.
#
# Bounded because the key is a model string, and a fine-tune id or a caller building
# names dynamically would otherwise grow it without limit. An agent talks to a handful
# of models, so the cap is never reached in practice; clearing wholesale when it is
# keeps the bookkeeping to nothing.
_PROVIDER_CACHE_MAX = 256
_provider_cache: dict[str, str | None] = {}


def _resolve_provider(model: str) -> str | None:
    """litellm's own provider for ``model``, or None when it cannot resolve one.

    ``get_llm_provider`` raises ``BadRequestError`` for a model it does not know
    (measured: ``claude-3-5-sonnet-latest`` raises, ``claude-sonnet-4-20250514`` does
    not), and a telemetry lookup must never be the reason a model call fails.

    Cached for two reasons beyond speed. litellm prints a red "Provider List: ..."
    banner to STDOUT when resolution fails — not through logging, so it cannot be
    filtered — and uncached, an agent on a model string litellm cannot place would
    print it on every single call. Redirecting stdout around the lookup was the
    alternative and is worse: it swaps a process-global for the duration, so under
    concurrency it would swallow output belonging to other coroutines.
    """
    if not model:
        return None
    if model in _provider_cache:
        return _provider_cache[model]

    provider: str | None = None
    try:
        from litellm import get_llm_provider

        _model, resolved, _key, _base = get_llm_provider(model=model)
        provider = resolved or None
    except Exception:
        provider = None

    if len(_provider_cache) >= _PROVIDER_CACHE_MAX:
        _provider_cache.clear()
    _provider_cache[model] = provider
    return provider


def resolve_model(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """The model for a litellm call, whether it arrived by keyword or positionally.

    ``litellm.acompletion`` takes ``model`` as its FIRST positional argument, and the
    gateway forwards ``*args`` untouched, so ``gateway.acompletion("anthropic/claude-
    sonnet-4", messages)`` is a legal call that puts the model in ``args[0]``.

    Reading only ``kwargs`` there does not merely mislabel the vendor, it loses the
    measurement: an empty model resolves to the default vendor "openai", which sets
    ``transport=OPENAI``, which makes ``call()`` stand down for the OpenAI client
    instrumentor — while litellm routes natively to Anthropic and never touches that
    client. Nothing records it and nothing says so.
    """
    model = kwargs.get("model")
    if not model and args:
        model = args[0]
    # Positional args are forwarded verbatim, so args[0] is whatever the caller passed;
    # only a string can be a litellm model name.
    return model if isinstance(model, str) else ""


def inference_call(kwargs: dict[str, Any], args: tuple[Any, ...] = ()) -> Any:
    """Begin recording one litellm call. Never raises, never returns None."""
    genai = _genai()
    if genai is None:
        return _NULL_CALL

    try:
        model = resolve_model(args, kwargs)
        vendor, over_openai_client = _split_model(model)
        return genai.call(
            provider=vendor,
            operation=genai.CHAT,
            model=model,
            # litellm normalises every vendor's response onto the OpenAI shape, so one
            # parser reads them all — which is exactly what `spec` separates from the
            # `provider` label.
            spec=genai.OPENAI_SPEC,
            transport=genai.OPENAI if over_openai_client else "",
        )
    except Exception:
        logger.debug("could not start a GenAI metrics record", exc_info=True)
        return _NULL_CALL


class _NullCall:
    """What call sites get when sgp-obs is absent. Records nothing, costs nothing."""

    def observe(self, response: Any) -> Any:
        return response

    # Underscored like __aexit__'s params below: present for parity with the real
    # sgp-obs call object, never read here.
    def failed(self, _error: BaseException) -> None:
        return

    async def __aenter__(self) -> "_NullCall":
        return self

    async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> bool:
        return False  # never suppress the caller's exception


_NULL_CALL = _NullCall()


def _reset_for_tests() -> None:
    """Forget the resolved module, so a test can present a different sgp-obs.

    The handle is a process-wide latch: without this, the first test to run with
    sgp-obs absent would cache None for the rest of the session and every later test
    that injects a fake ``sgp_obs.metrics`` would silently exercise the null path.
    """
    global _genai_module, _openai_client_providers
    _genai_module = _GENAI_UNRESOLVED
    _openai_client_providers = _OPENAI_CLIENT_PROVIDERS_UNRESOLVED
    _provider_cache.clear()
