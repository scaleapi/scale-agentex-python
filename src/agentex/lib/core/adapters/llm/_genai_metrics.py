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
:func:`_transport_for`.

Everything here is fail-open: sgp-obs is an optional dependency and a telemetry problem
must never fail a model call. If the import fails, :func:`inference_call` returns an
object that records nothing and costs nothing.
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

_warned = False


def _split_model(model: str) -> tuple[str, bool]:
    """``(vendor, goes_out_over_the_openai_client)`` for a litellm model string.

    ``"litellm_proxy/anthropic/claude-sonnet-4"`` -> ``("anthropic", True)``
    ``"anthropic/claude-sonnet-4"``              -> ``("anthropic", False)``
    ``"gpt-4o"``                                 -> ``("openai", True)``

    A bare name is OpenAI, and litellm reaches OpenAI through the ``openai``
    client, so the client instrumentor already sees it and we stand down.
    """
    proxied = model.startswith(_PROXY_PREFIX)
    rest = model[len(_PROXY_PREFIX):] if proxied else model
    vendor = rest.split("/", 1)[0] if "/" in rest else _DEFAULT_VENDOR
    # Proxy mode always leaves over the OpenAI client. So does a native openai/* call.
    return (vendor or _DEFAULT_VENDOR), proxied or vendor == _DEFAULT_VENDOR


def inference_call(kwargs: dict[str, Any]) -> Any:
    """Begin recording one litellm call. Never raises, never returns None."""
    try:
        # See sgp_obs_setup.py: optional, not publicly installable, absent in CI.
        from sgp_obs.metrics import genai  # type: ignore[import-not-found]
    except Exception:
        global _warned
        if not _warned:
            _warned = True
            logger.debug(
                "sgp-obs is not available; GenAI metrics are off for litellm calls"
            )
        return _NULL_CALL

    try:
        model = kwargs.get("model") or ""
        vendor, over_openai_client = _split_model(str(model))
        return genai.call(
            provider=vendor,
            operation=genai.CHAT,
            model=str(model),
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
