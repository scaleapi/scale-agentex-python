# Tutorial 060: Sync Claude Code Agent

This tutorial demonstrates how to build a **synchronous** agent that spawns the
Claude Code CLI as a local subprocess and streams its output through the Agentex
unified harness surface via ``ClaudeCodeTurn`` and ``UnifiedEmitter``.

## Key Concepts

### ClaudeCodeTurn + UnifiedEmitter

``ClaudeCodeTurn`` wraps ``convert_claude_code_to_agentex_events``, which
parses the newline-delimited JSON envelopes emitted by
``claude -p --output-format stream-json``. It implements the ``HarnessTurn``
protocol: an ``events`` async iterator of canonical ``StreamTaskMessage*``
objects and a ``usage()`` method (populated once the stream is exhausted).

``UnifiedEmitter.yield_turn(turn)`` is the sync delivery path: it forwards
events as HTTP yield chunks while tracing as a side effect.

### Local subprocess spawn

The ``_spawn_claude`` function in ``project/acp.py`` uses
``asyncio.create_subprocess_exec`` to run:

```
claude -p --output-format stream-json --verbose
```

The prompt is written to stdin. Stdout is read line by line and fed into
``ClaudeCodeTurn``. This is purely local -- no Scale sandbox is involved.

Production isolation (Scale sandbox, secret injection, MCP configuration)
is the golden agent's concern at
``teams/sgp/agents/golden_agent/project/harness/providers/claude.py``.

### Injectable spawn seam

``_spawn_claude`` is a top-level async generator in ``project/acp.py``.
Tests monkeypatch it to inject pre-recorded stream-json lines instead of
spawning the real process, so offline unit tests run without the CLI.

## Files

| File | Description |
|------|-------------|
| ``project/acp.py`` | ACP server, ``_spawn_claude`` seam, and message handler |
| ``tests/test_agent.py`` | Live integration tests (needs CLI + API key) |
| ``tests/test_agent_offline.py`` | Offline unit tests with injected fake subprocess |
| ``manifest.yaml`` | Agent configuration |

## Running Locally (live)

Requires the ``claude`` CLI installed and ``ANTHROPIC_API_KEY`` set:

```bash
npm install -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY=sk-ant-...
agentex agents run
```

## Running Offline Tests

No CLI or API key needed:

```bash
uv run pytest tests/test_agent_offline.py -v
```

## Notes

- Production isolation (sandbox, secrets, MCP) is the golden agent's concern.
  This tutorial runs the CLI directly to keep the code as simple as possible.
- Multi-turn session resumption (``claude -r <session_id>``) is out of scope
  for this tutorial. See the golden agent for that pattern.
- The ``--verbose`` flag is included to match the golden agent's invocation;
  it causes the CLI to emit ``stream_event`` triples for incremental streaming.
