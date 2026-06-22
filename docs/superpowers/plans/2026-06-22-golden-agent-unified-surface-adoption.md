# Golden Agent — Adopting the Unified Harness Surface

Date: 2026-06-22
Status: Plan (implementation lands in `agentex-agents`, after the SDK stack merges + releases)
SDK repo: `scale-agentex-python` · Agent repo: `agentex-agents` (`teams/sgp/agents/golden_agent`)

## Goal

Replace the golden agent's bespoke harness internals (its neutral `HarnessEvent` vocabulary, the `AgentexStreamAdapter`, and the per-provider stream parsers) with the now-first-class SDK unified surface — `convert_<harness>_to_agentex_events` taps + `<Harness>Turn` + `UnifiedEmitter` — while keeping every SGP-coupled orchestration concern (sandbox pool, sandbox setup, secret/MCP reauth, data-plane override) exactly where it is. Net effect: the golden agent stops maintaining its own parsing/streaming/tracing layer and consumes the SDK's, which now carries the AGX1-377/378 fixes and cross-channel conformance.

This is the payoff of the SDK harness-surface workstream (PRs: foundation #412, conformance #414, pydantic #415, openai #416, langgraph #417, claude-code #420, codex #421). The SDK *enables* the surface; this plan *consumes* it in production.

## Current golden-agent internals (what gets replaced vs kept)

Paths under `teams/sgp/agents/golden_agent/project/`.

| Area | File(s) | Disposition |
|------|---------|-------------|
| Neutral event vocabulary | `harness/events.py` (`HarnessEvent`) | **Delete** — superseded by the SDK canonical `StreamTaskMessage*` stream. |
| Event→adk bridge | `harness/adapter.py` (`AgentexStreamAdapter`) | **Delete** — superseded by `UnifiedEmitter` (yield + auto_send) which drives `adk.streaming`/`adk.tracing` and derives spans. |
| Provider protocol | `harness/protocol.py` (`HarnessProvider`) | **Delete or shrink** — providers no longer need to emit `HarnessEvent`; they produce the CLI's stdout stream and hand it to the SDK tap. |
| claude-code parser | `harness/providers/claude.py` `_StreamJsonProcessor` | **Delete** — replaced by SDK `convert_claude_code_to_agentex_events` + `ClaudeCodeTurn`. Keep the sandbox/CLI-spawn parts of `ClaudeProvider`. |
| codex parser | `harness/providers/codex.py` `_CodexEventProcessor` | **Delete** — replaced by SDK `convert_codex_to_agentex_events` + `CodexTurn`. Keep sandbox/CLI-spawn. |
| Turn dispatch activity | `harness/activity.py` (`execute_agent_turn`) | **Simplify** — keep provider selection + heartbeat + metrics; replace the `provider→HarnessEvent→adapter` loop with `tap → <Harness>Turn → UnifiedEmitter.auto_send_turn`. |
| In-process OpenAI-Agents harness | `harness/oai_mcp.py`, `oai_hooks.py`, `oai_streaming_model.py` | **Phase 4 (optional)** — could adopt the SDK openai tap; trickiest, deferred. |
| Sandbox pool / setup / config / data-plane | `sandbox_pool.py`, `sandbox_setup.py`, `sandbox_config.py`, `sandbox_client_oai.py`, `pool_activities.py` | **Keep unchanged** (SGP-coupled; out of SDK scope). |
| Secret / MCP reauth | `secrets.py`, `internal-packages/sgp_secrets_client` | **Keep unchanged** (SGP/identity-service-coupled). |
| Capabilities / catalog / prompts / workflow / cron | `capabilities/*`, `prompts/*`, `workflow.py`, `cron.py`, `meta_activities.py` | **Keep unchanged.** |
| Reconnect notices | `harness/notices.py` | **Keep** — independent of the harness stream (a standalone task message). |

## Target flow (per turn, inside the Temporal activity)

The golden agent runs under Temporal, so delivery uses the **auto_send** channel from inside the activity (the SDK `UnifiedEmitter.auto_send_turn`, which already runs correctly in an activity).

```
# workflow side: capture the timestamp in workflow context and pass it in,
# because workflow.now() is NOT available inside an activity.
execute_agent_turn(ActivityParams(..., created_at=workflow.now()))

execute_agent_turn (activity, receives created_at via ActivityParams):
  1. Acquire/reconnect sandbox (pool), resolve secrets, render MCP config   # KEEP — SGP-coupled
  2. Emit sandbox-setup steps as ToolRequestContent/ToolResponseContent      # KEEP — now agentex content
  3. Spawn `claude -p --output-format stream-json` / `codex exec` in sandbox # KEEP — CLI spawn
  4. turn = ClaudeCodeTurn(chain(setup_events, convert_claude_code_to_agentex_events(sandbox.stdout_lines)))  # NEW — SDK tap + Turn
  5. result = await UnifiedEmitter(task_id, trace_id, parent_span_id)\
                      .auto_send_turn(turn, created_at=params.created_at)     # NEW — SDK delivery
  6. emit per-turn metrics from result.usage (TurnUsage)                      # KEEP — DogStatsD, now fed by TurnUsage
```

### Sandbox-setup event interleaving
Today the provider yields sandbox provisioning steps (reconnect / find / create / configure-git / clone) as `ToolStarted`/`ToolCompleted` `HarnessEvent`s that flow through the adapter so they appear in the UI + trace. Under the unified surface these become agent-produced `ToolRequestContent`/`ToolResponseContent` `StreamTaskMessage*` messages, **chained before** the harness tap's stream into one canonical stream for the turn (`chain(setup_events, convert_claude_code_to_agentex_events(stdout))`). `UnifiedEmitter` then delivers and traces the whole turn uniformly — setup steps keep showing in the UI and span tree.

### Determinism / timestamps
Capture the timestamp in the **workflow** with `workflow.now()` and pass it into `execute_agent_turn` as an activity parameter (`created_at`); the activity forwards `params.created_at` to `auto_send_turn` (AGX1-378) so the turn's messages carry deterministic Temporal timestamps, matching the prior dispenser behavior. Do NOT call `workflow.now()` inside the activity (it is only valid in workflow context and raises otherwise).

### Usage / metrics
`auto_send_turn` returns a `TurnResult` with a normalized `TurnUsage`. The golden agent's per-turn DogStatsD metrics (`metrics.py`) read from `TurnUsage` instead of the old `TurnCompleted` event — one shape for traces + metrics.

## Phases

**Phase 0 — Prereqs (no golden-agent code yet)**
- SDK stack merges to `next`/main and a version is released (or pin a pre-release).
- Confirm the public import path (AGX1-375): import the surface from the public `adk.*` facade if available, else `agentex.lib.core.harness` / `adk._modules`.
- Bump the golden agent's `scale-agentex` dependency to that version. Watch the `uv.lock` churn (commit it deliberately; see the team's lint-before-push rule).

**Phase 1 — claude-code provider**
- In `ClaudeProvider`, keep sandbox acquisition, secret/MCP injection, and the `claude -p` spawn. Replace the `_StreamJsonProcessor` + `HarnessEvent` yielding with: produce the CLI's stdout as an async line iterator and wrap it in `ClaudeCodeTurn`.
- In `execute_agent_turn`, replace the `AgentexStreamAdapter` loop with `UnifiedEmitter(...).auto_send_turn(turn, created_at=params.created_at)` (the calling workflow passes `workflow.now()` into the activity params; see "Determinism / timestamps"); chain the sandbox-setup content before the tap stream.
- Delete `_StreamJsonProcessor`.
- Verify against the golden agent's existing turn tests + a live claude-code turn in a dev sandbox: UI streaming, tool spans, reasoning, usage/metrics all intact.

**Phase 2 — codex provider** — same as Phase 1 with `convert_codex_to_agentex_events` + `CodexTurn`; delete `_CodexEventProcessor`.

**Phase 3 — retire the bespoke harness layer** — delete `harness/events.py`, `harness/adapter.py`, and shrink/delete `harness/protocol.py`; simplify `harness/activity.py` to the tap→Turn→emitter shape. Confirm no remaining imports of the deleted symbols.

**Phase 4 (optional, later) — in-process OpenAI-Agents (litellm) harness** — adopt the SDK openai tap (`OpenAITurn` / `run_agent_streamed_auto_send`) in place of `oai_streaming_model.py`/`oai_hooks.py`. This path runs the OpenAI Agents SDK in-process inside the workflow and is the most coupled to Temporal context; treat as a separate, carefully-scoped follow-up.

## Testing
- The SDK's cross-channel conformance (#414) + per-harness fixtures already prove the taps produce correct, channel-equivalent streams + spans + usage. The golden agent inherits that confidence by consuming them.
- Golden-agent side: keep its existing turn/integration tests; add a dev-sandbox live smoke per provider (claude-code, codex) asserting streamed text + tool request/response + reasoning + a well-formed span tree + non-zero `TurnUsage`.
- Regression watch: UI message shapes (text/reasoning/tool), span nesting, and per-turn metrics must match pre-migration behavior.

## What stays SGP-side permanently (never moves to the SDK)
Per the original layering analysis: the sandbox pool + acquire modes, sandbox setup orchestration, `_override_data_plane` (ARP in-cluster routing), the sgp-secrets client, and user-scoped secret resolution / OAuth MCP reauth. The reauth refresh ideally migrates **identity-service-side** over time (so the agent becomes a dumb consumer of live tokens); the SDK only needs a generic "credential expired → emit reconnect notice" hook, not the sgp-secrets contract.

## Risks / watch-items
- **Wire-shape parity:** the SDK `auto_send` delivers `Full` tool messages as open+close and streamed tool requests as `Start+Delta+Done` (both deliver equivalent content; AGX1-377 fixed the previously-dropped streamed shape). Validate the UI renders tool request/response identically to today.
- **Reasoning/thinking mapping:** confirm claude-code `thinking` blocks and codex reasoning map to `ReasoningContent` the same way the old adapter did (the SDK taps were ported from these exact processors, so parity is expected — verify in a live turn).
- **Heartbeat/timeout:** keep `execute_agent_turn`'s heartbeat pulse around the (now SDK-driven) consumption loop; long CLI turns must still heartbeat.
- **uv.lock / dependency bump:** pin the SDK version explicitly; deliberate lock commit.

## Sequencing summary
SDK PRs merge + release → bump golden agent dependency (Phase 0) → claude-code (Phase 1) → codex (Phase 2) → delete bespoke harness layer (Phase 3) → optional in-process OpenAI-Agents adoption (Phase 4). Each phase is independently shippable and reversible (the deleted code is recoverable from history until Phase 3 lands).
