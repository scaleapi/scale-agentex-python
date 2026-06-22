# Tutorial 130 (async/base): Async Claude Code Agent

This tutorial demonstrates how to build an **async (non-Temporal)** agent that
spawns the Claude Code CLI as a local subprocess and delivers its output through
the Agentex unified harness surface via ``ClaudeCodeTurn`` and
``UnifiedEmitter.auto_send_turn``.

## Key Concepts

### Async delivery path

Unlike the sync tutorial (060), this agent uses the async ACP model. The
``@acp.on_task_event_send`` handler does not return a generator -- instead,
``UnifiedEmitter.auto_send_turn(turn)`` pushes events to the task's Redis
stream in real time and returns a ``TurnResult`` when the turn is complete.
The UI polls or streams that Redis channel independently.

### ClaudeCodeTurn + UnifiedEmitter

Same tap as the sync tutorial:
- ``ClaudeCodeTurn`` wraps ``convert_claude_code_to_agentex_events``.
- ``UnifiedEmitter`` wires trace context + chosen delivery.
- ``auto_send_turn`` is the async push path.

### Local subprocess spawn

``_spawn_claude`` in ``project/acp.py`` uses ``asyncio.create_subprocess_exec``
to run:

```
claude -p --output-format stream-json --verbose
```

The prompt is written to stdin. Stdout is read line by line.

Production isolation (Scale sandbox, secret injection, MCP configuration)
is the golden agent's concern at
``teams/sgp/agents/golden_agent/project/harness/providers/claude.py``.

### Injectable spawn seam

``_spawn_claude`` is a top-level async generator. Tests monkeypatch it to
inject pre-recorded stream-json lines so offline unit tests run without the CLI.

## Files

| File | Description |
|------|-------------|
| ``project/acp.py`` | ACP server, ``_spawn_claude`` seam, and event handler |
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
- For multi-turn memory, persist the Claude Code session_id from the
  ``result`` envelope and pass it to ``claude -r <session_id>`` on the next turn.
