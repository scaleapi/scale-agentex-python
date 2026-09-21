# Tutorial 140 (async/temporal): Temporal Claude Code Agent

This tutorial demonstrates how to build a **Temporal-backed** agent that
spawns the Claude Code CLI as a local subprocess and delivers its output
through the Agentex unified harness surface via ``ClaudeCodeTurn`` and
``UnifiedEmitter.auto_send_turn``, with Temporal providing durable execution
and crash recovery.

## Key Concepts

### Temporal + ClaudeCodeTurn

The Temporal workflow (``project/workflow.py``) holds state durably. Each user
message arrives as a signal (``on_task_event_send``), spawns the Claude Code
CLI locally, wraps the stdout line stream in ``ClaudeCodeTurn``, and pushes
events to the task's Redis stream via ``UnifiedEmitter.auto_send_turn``.

``workflow.now()`` is passed as ``created_at`` so message timestamps are
deterministic under Temporal replay.

### Multi-turn session resume

The workflow persists the Claude Code ``session_id`` from the ``result``
envelope. On the next turn, ``-r <session_id>`` is passed to the CLI to
resume the conversation. Temporal's durable state ensures the session_id
survives worker crashes.

### Note on subprocess in workflow code

For simplicity, this tutorial spawns the subprocess directly inside the
workflow signal handler. For production use, move the spawn into a custom
Temporal activity so each subprocess invocation gets independent retry and
timeout guarantees. See
``examples/tutorials/10_async/10_temporal/030_custom_activities/`` for
that pattern.

### Injectable spawn seam

``_spawn_claude`` in ``project/workflow.py`` is a top-level async generator.
Tests monkeypatch it to inject pre-recorded stream-json lines so offline
unit tests run without the CLI.

## Files

| File | Description |
|------|-------------|
| ``project/acp.py`` | Thin ACP server; wires Temporal (no handlers) |
| ``project/workflow.py`` | Temporal workflow + ``_spawn_claude`` seam |
| ``project/run_worker.py`` | Temporal worker entry point |
| ``tests/test_agent.py`` | Live integration tests (needs CLI + Temporal + API key) |
| ``tests/test_agent_offline.py`` | Offline unit tests with injected fake subprocess |
| ``manifest.yaml`` | Agent configuration |

## Running Locally (live)

Requires Temporal server, the ``claude`` CLI, and ``ANTHROPIC_API_KEY``:

```bash
npm install -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY=sk-ant-...
agentex agents run
```

## Running Offline Tests

No CLI, Temporal, or API key needed:

```bash
uv run pytest tests/test_agent_offline.py -v
```

## Notes

- Production isolation (sandbox, secrets, MCP) is the golden agent's concern.
- The subprocess spawn should be moved to a custom activity in production.
- The ``--verbose`` flag is included to match the golden agent's invocation.
