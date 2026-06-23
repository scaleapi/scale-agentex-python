"""Back-compat shim: ``OpenAITurn`` and ``openai_usage_to_turn_usage`` now live
in ``agentex.lib.adk._modules._openai_turn``.

Existing importers of
``agentex.lib.adk.providers._modules.openai_turn.{OpenAITurn,openai_usage_to_turn_usage}``
keep working.
"""

from agentex.lib.adk._modules._openai_turn import (  # noqa: F401
    OpenAITurn,
    openai_usage_to_turn_usage,
)
