# harness_codex (Temporal)

Tutorial agent demonstrating the `convert_codex_to_agentex_events` tap,
`CodexTurn`, and `UnifiedEmitter` for a **Temporal-durable** async ACP agent.

## What this tutorial shows

- Spawning `codex exec --json` as a **local asyncio subprocess** (no Scale sandbox)
  inside a Temporal workflow signal handler.
- Wrapping the stdout line stream in a `CodexTurn`.
- Delivering every canonical `StreamTaskMessage*` event to Redis via
  `UnifiedEmitter.auto_send_turn`, passing `created_at=workflow.now()` for
  deterministic Temporal replay timestamps.
- Keeping the codex thread ID on the workflow instance (durable across crashes
  without an external `adk.state` round-trip).

> **Production isolation note:** A tutorial agent runs the Codex CLI locally.
> Production-grade isolation (Scale sandbox, secret injection, MCP configuration)
> is handled by the golden agent at
> `teams/sgp/agents/golden_agent/project/harness/providers/codex.py`.

> **Temporal determinism note:** Subprocess spawning happens inside
> `@workflow.signal` handler bodies. Temporal does NOT replay signal handler
> bodies (only `@workflow.run` is subject to replay constraints), so this is
> safe. A production agent would wrap the subprocess in a Temporal activity for
> full durability and retry semantics.

## Live runs

Live runs require:
1. The `codex` CLI on PATH: `npm install -g @openai/codex`
2. `OPENAI_API_KEY` set in the environment.
3. A running Temporal server.

## Running offline unit tests

```bash
cd /path/to/scale-agentex-python
uv run --all-packages --all-extras pytest examples/tutorials/10_async/10_temporal/harness_codex/tests/test_agent.py -q
```

## Running live integration tests

```bash
export CODEX_LIVE_TESTS=1
export OPENAI_API_KEY=sk-...
pytest tests/test_agent.py -v
```
