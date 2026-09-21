"""Cross-channel conformance tests for the claude-code parser tap.

Each fixture is a representative sequence of claude-code stream-json
envelopes, converted into canonical ``StreamTaskMessage*`` events via
``ClaudeCodeTurn``, then registered into the shared conformance runner.

The conformance runner asserts two guarantees per fixture:

1. **Logical-delivery equivalence**: ``yield_events`` and ``auto_send``
   produce the same logically-delivered message contents.

2. **Span signal equivalence**: both channels emit the same ``SpanSignal``
   sequence to their ``SpanTracer``.

Fixtures
--------
text-only:       single ``assistant`` text block
tool-call-result: ``tool_use`` block followed by ``tool_result``
thinking-block:  ``thinking`` block with full text
multi-step:      text + tool_use + tool_result + text (two model turns)

Note
----
Relative imports are used throughout (runner.py and these fixtures live in the
same package). The per-module ``_FIXTURES`` list is both registered globally
(via ``register()``) and parametrized locally so this module's tests are
self-contained regardless of global registry ordering (see runner.py docstring).
"""

from __future__ import annotations

import pytest

from agentex.lib.adk._modules._claude_code_sync import convert_claude_code_to_agentex_events

from .runner import (
    Fixture,
    register,
    run_pure_async,
    run_cross_channel_conformance,
)

# ---------------------------------------------------------------------------
# Convert claude-code envelopes to StreamTaskMessage* events
# ---------------------------------------------------------------------------


async def _envelopes_to_events(envelopes: list[dict]) -> list:
    """Drive convert_claude_code_to_agentex_events and collect all events."""

    async def _aiter(items):  # type: ignore[return]
        for item in items:
            yield item

    return [e async for e in convert_claude_code_to_agentex_events(_aiter(envelopes))]


# ---------------------------------------------------------------------------
# Fixture definitions (raw claude-code envelope sequences)
# ---------------------------------------------------------------------------

_TEXT_ENVELOPES = [
    {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "The answer is 42."}]},
    }
]

_TOOL_ENVELOPES = [
    {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_read",
                    "name": "Read",
                    "input": {"path": "/workspace/README.md"},
                }
            ]
        },
    },
    {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_read",
                    "content": "# My Project\n\nA great project.",
                }
            ]
        },
    },
]

_THINKING_ENVELOPES = [
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "thinking", "thinking": "Let me think about this carefully.\nStep 1: check the facts."},
                {"type": "text", "text": "Here is my answer."},
            ]
        },
    }
]

_MULTI_STEP_ENVELOPES = [
    # Turn 1: text + tool call
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Let me look that up."},
                {
                    "type": "tool_use",
                    "id": "call_bash",
                    "name": "Bash",
                    "input": {"command": "cat /etc/hostname"},
                },
            ]
        },
    },
    {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_bash",
                    "content": "myhost",
                }
            ]
        },
    },
    # Turn 2: final text after tool result
    {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "The hostname is myhost."}]},
    },
]


# ---------------------------------------------------------------------------
# Build fixtures from envelopes at module load time
# ---------------------------------------------------------------------------


async def _build_fixture(name: str, envelopes: list[dict]) -> Fixture:
    events = await _envelopes_to_events(envelopes)
    return Fixture(name=name, events=events)


# Fixtures must exist before pytest collects (they parametrize the test below),
# so they are built at import time. The conversion only iterates in-memory
# envelopes — it never suspends on a real future — so we drive the coroutines to
# completion with the shared loop-free ``run_pure_async`` driver instead of
# asyncio.run(), which raises RuntimeError at import when an event loop is
# already running (programmatic pytest, a Jupyter kernel, or session-scoped
# asyncio loops).
_FIXTURES: list[Fixture] = [
    run_pure_async(_build_fixture("claude-code-text-only", _TEXT_ENVELOPES)),
    run_pure_async(_build_fixture("claude-code-tool-call-result", _TOOL_ENVELOPES)),
    run_pure_async(_build_fixture("claude-code-thinking-block", _THINKING_ENVELOPES)),
    run_pure_async(_build_fixture("claude-code-multi-step", _MULTI_STEP_ENVELOPES)),
]

# Register into the shared registry so all_fixtures() can enumerate them
for _f in _FIXTURES:
    register(_f)


# ---------------------------------------------------------------------------
# Cross-channel conformance assertions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.name)
@pytest.mark.asyncio
async def test_cross_channel_equivalence(fixture: Fixture) -> None:
    """yield_events and auto_send must produce equivalent logical deliveries
    and identical span signals for every claude-code fixture.
    """
    yield_deliveries, auto_deliveries, yield_spans, auto_spans = await run_cross_channel_conformance(fixture)

    assert yield_deliveries == auto_deliveries, (
        f"[{fixture.name}] logical deliveries differ:\n  yield:     {yield_deliveries}\n  auto_send: {auto_deliveries}"
    )
    assert yield_spans == auto_spans, (
        f"[{fixture.name}] span signals differ:\n  yield:     {yield_spans}\n  auto_send: {auto_spans}"
    )
