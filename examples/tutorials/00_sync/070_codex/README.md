# 070_codex (sync)

Tutorial agent demonstrating the `convert_codex_to_agentex_events` tap,
`CodexTurn`, and `UnifiedEmitter` for a **sync** (HTTP-yield) ACP agent.

## What this tutorial shows

- Spawning `codex exec --json` as a **local asyncio subprocess** (no Scale sandbox).
- Wrapping the stdout line stream in a `CodexTurn`.
- Delivering every canonical `StreamTaskMessage*` event to the HTTP caller via
  `UnifiedEmitter.yield_turn` (tracing as a side-effect).

> **Production isolation note:** A tutorial agent runs the Codex CLI locally.
> Production-grade isolation (Scale sandbox, secret injection, MCP configuration)
> is handled by the golden agent at
> `teams/sgp/agents/golden_agent/project/harness/providers/codex.py`.

## Live runs

Live runs require:
1. The `codex` CLI on PATH: `npm install -g @openai/codex`
2. `OPENAI_API_KEY` set in the environment.

## Running offline unit tests

The offline tests inject a fake subprocess and never invoke the real CLI:

```bash
cd /path/to/scale-agentex-python
uv run --all-packages --all-extras pytest examples/tutorials/00_sync/070_codex/tests/test_agent.py -q
```

## Running live integration tests

```bash
export CODEX_LIVE_TESTS=1
export OPENAI_API_KEY=sk-...
# Start the agent server first, then:
pytest tests/test_agent.py -v
```
