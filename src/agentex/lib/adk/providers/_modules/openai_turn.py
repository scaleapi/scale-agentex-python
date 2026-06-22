"""Back-compat shim: ``OpenAITurn`` now lives in
``agentex.lib.adk._modules._openai_turn``.

Existing importers of
``agentex.lib.adk.providers._modules.openai_turn.OpenAITurn`` keep working.
"""

from agentex.lib.adk._modules._openai_turn import OpenAITurn  # noqa: F401
