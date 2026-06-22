# harness_codex (async base)

Tutorial agent demonstrating the `convert_codex_to_agentex_events` tap,
`CodexTurn`, and `UnifiedEmitter` for an **async** (Redis-streaming, no Temporal)
ACP agent.

## What this tutorial shows

- Spawning `codex exec --json` as a **local asyncio subprocess** (no Scale sandbox).
- Wrapping the stdout line stream in a `CodexTurn`.
- Delivering every canonical `StreamTaskMessage*` event to Redis via
  `UnifiedEmitter.auto_send_turn`, so the UI receives tokens in real time.
- Persisting the codex thread ID in `adk.state` so subsequent turns resume the
  same codex session via `codex exec resume <thread_id>`.

> **Production isolation note:** A tutorial agent runs the Codex CLI locally.
> Production-grade isolation (Scale sandbox, secret injection, MCP configuration)
> is handled by the golden agent at
> `teams/sgp/agents/golden_agent/project/harness/providers/codex.py`.

## Live runs

Live runs require:
1. The `codex` CLI on PATH: `npm install -g @openai/codex`
2. `OPENAI_API_KEY` set in the environment.

## Running offline unit tests

```bash
cd /path/to/scale-agentex-python
uv run --all-packages --all-extras pytest examples/tutorials/10_async/00_base/harness_codex/tests/test_agent.py -q
```

## Running live integration tests

```bash
export CODEX_LIVE_TESTS=1
export OPENAI_API_KEY=sk-...
pytest tests/test_agent.py -v
```
