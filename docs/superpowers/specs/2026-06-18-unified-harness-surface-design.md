# Unified Harness Tracing / Message-Emitting Surface

Date: 2026-06-18
Status: Approved design, pending implementation
Repo: `scale-agentex-python`

## Problem

The SDK integrates several agent harnesses (pydantic-ai, LangGraph, OpenAI Agents) by
converting each harness's native output into Agentex `StreamTaskMessage*` events. Today
that integration is triplicated per harness:

- `_<harness>_sync.py` — a converter that **yields** Agentex events back over the
  HTTP/JSON-RPC response (sync ACP agents).
- `_<harness>_async.py` — a converter that **auto-sends** to the task stream (Redis via
  `adk.streaming`) for async + temporal agents.
- `_<harness>_tracing.py` — a separate, opt-in tracing handler wired into the converter
  by hand.

Consequences:

- The native-output → Agentex-event mapping exists in two places per harness (sync and
  async) and can drift.
- Tracing is bolted on per harness and is inconsistent across harnesses.
- There is no shared notion of a tool/reasoning span tree or turn-level metadata.
- The golden agent grew a parallel "harness layer" (a neutral `HarnessEvent` vocabulary
  plus an adapter that drives `adk.streaming` + `adk.tracing`) to solve the same problem
  for its subprocess CLI harnesses (claude-code, codex). That logic is valuable but lives
  outside the SDK.

## Goal (end state)

pydantic-ai, LangGraph, OpenAI Agents, claude-code, and codex all emit through one unified
surface. A single pass over a harness's output drives **streaming, message persistence, and
tracing** from one source of truth, in the same shape as Agentex events. The surface works
for **both** delivery channels (sync yield, async/temporal auto-send). Tracing is on by
default and overridable. The claude-code/codex *parsers* live in the SDK; their sandbox /
secret / MCP orchestration stays in the golden agent.

## Approach: Agentex event stream is canonical (Approach A)

The Agentex `StreamTaskMessage*` stream is the single source of truth. Each harness maps its
native output to that stream **once**. A single emitter consumes that one stream and fans it
out to delivery (yield or auto-send) and to tracing (spans derived from the same stream).

We considered two alternatives and rejected them:

- **Neutral `AgentEvent` vocabulary + dual projectors (Approach B):** richer (carries turn
  usage/cost natively, clean start/end pairing) but reintroduces a parallel vocabulary to
  keep in sync with Agentex types, for the same outcome.
- **Push-to-sink with typed emitter methods (Approach C):** very testable, but the *yield*
  delivery channel fights a push API (needs a queue/generator bridge), and sync ACP agents
  depend on yield.

Approach A matches "same shape as Agentex events" most directly, makes the yield channel
free, and lets us delete the per-harness tracing code by deriving spans from the canonical
stream.

## Components

Four shared, harness-independent components plus one thin tap per harness.

### 1. Per-harness tap (the only per-harness code)

```
convert_<harness>_to_agentex_events(native_stream, ...) -> AsyncIterator[StreamTaskMessage*]
```

The existing sync converters (`convert_pydantic_ai_to_agentex_events`,
`convert_langgraph_to_agentex_events`, `convert_openai_to_agentex_events`) already have this
shape and *become* the taps. New taps: `convert_claude_code_to_agentex_events`,
`convert_codex_to_agentex_events` (pure parsers over the CLIs' newline-delimited
stream-json; no SGP/sandbox coupling).

### 2. Auto-send adapter (shared)

Consumes the canonical Agentex stream and drives `adk.streaming` context managers: open/close
text and reasoning contexts, switch cleanly between them, stream tool request/response. This
generalizes the golden agent's `AgentexStreamAdapter` and replaces the N hand-written
`_async` bodies with one. Returns the accumulated final text (preserving current
auto-send return values).

### 3. Yield adapter (shared)

Passes the canonical stream through to the caller (sync HTTP ACP), tee-ing each event to the
tracer as a side effect.

### 4. Tracing tap (shared)

A stateful reducer that derives spans from the canonical stream. It only *observes*
`index` and `tool_call_id`; it never mutates or reorders the stream, so streaming fidelity
is unchanged.

Derivation rules:

- **Tool span open:** on `StreamTaskMessageDone` for an index whose `Start` content was a
  `ToolRequestContent`. Arguments are fully known by `Done` (covers both streamed-args and
  one-shot tools). The open span is keyed by `tool_call_id`.
- **Tool span close:** on `StreamTaskMessageFull(ToolResponseContent)` matching by
  `tool_call_id`.
- **Parallel / interleaved tools:** `ToolRequestContent`, `ToolResponseContent`,
  `ToolRequestDelta`, and `ToolResponseDelta` all carry `tool_call_id` + `name`, so multiple
  open tool spans pair correctly regardless of arrival order.
- **Reasoning span:** `Start(ReasoningContent)` → `Done` on that index.
- **Subagent span:** the Task/Agent tool's span (a tool span by another name), nested under
  the turn span.

Default-on whenever a trace context exists; **overridable** by passing a custom tracer, or
`None` to disable. Replaces the per-harness `_tracing.py` handlers.

**Open decision — tool error status.** `ToolResponseContent` currently has no
`is_error`/`status` field (only `content`), so a derived tool span cannot mark failure. The
golden agent's `ToolCompleted` carried `is_error`. Recommended resolution: add an additive
optional `is_error: bool | None` to `ToolResponseContent`. This is a generated type, so it is
a small upstream API-spec change (tracked as a prerequisite to the relevant migration PR), not
a local edit. Until it lands, derived spans omit tool error status rather than inferring it.

### Facade

A `UnifiedEmitter` ties the chosen delivery adapter and the tracer together so an agent
author calls one thing.

### Proposed layout

- Shared components: `src/agentex/lib/core/harness/` (delivery adapters, tracing tap, span
  derivation, facade).
- Taps: remain in `src/agentex/lib/adk/_modules/`.
- Public access: via the `adk` facade.

## Data flow

One pass over the canonical stream, fanned out by delivery mode.

- **Sync agent:** `async for ev in emitter.yield_events(convert_X(native)): ...` — the tracer
  observes each event; the event is yielded over the HTTP/JSON-RPC response.
- **Async + temporal agent:** `await emitter.auto_send(convert_X(native), task_id=...)` — the
  auto-send adapter pushes deltas to Redis via `adk.streaming` while the tracer observes the
  same events; returns accumulated final text. Temporal is identical, called from inside an
  activity (converters run in activities, not workflows, so determinism is not a concern).
- **Tracing** is the same derivation in both modes (it observes the canonical stream), so
  sync and auto-send produce identical spans.
- **Turn-level metadata** (usage / cost / model) is not an Agentex event, so it is surfaced
  as a first-class `TurnUsage` shape rather than ad-hoc data (see below).

Net dedup: **3 files × N harnesses → 1 tap × N harnesses + 3 shared components.**

## Unified turn usage / cost

Turn metadata is a first-class, harness-independent shape attached to the turn span and
returned to the caller — not a loose side-channel.

```
class TurnUsage(BaseModel):
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None   # subset of input_tokens served from cache
    reasoning_tokens: int | None      # subset of output_tokens
    total_tokens: int | None
    cost_usd: float | None
    duration_ms: int | None           # wall-clock, measured by the emitter
    num_llm_calls: int
    num_tool_calls: int               # derived from the canonical stream
    num_reasoning_blocks: int         # derived from the canonical stream

class TurnResult(BaseModel):
    final_text: str
    usage: TurnUsage
```

- Token field names align with the existing `agentex.lib.core.observability.llm_metrics`
  taxonomy (`input_tokens` / `output_tokens` / `cached_input_tokens` / `reasoning_tokens`),
  not a new vocabulary. (The OpenAI-style `llm_messages.Usage` —
  `prompt_tokens`/`completion_tokens` — is mapped into this richer shape.)
- **Each harness tap normalizes its native usage** into `TurnUsage`: pydantic-ai
  `result.usage()`, LangGraph `usage_metadata`, OpenAI `response.usage`, claude-code/codex
  the final `result` envelope (`cost_usd` + usage). Per-harness normalization, one output
  shape.
- The stream-derived counts (`num_tool_calls`, `num_reasoning_blocks`) come for free from the
  tracing tap's reduction; `duration_ms` is measured by the emitter; tokens/cost/model come
  from the tap's native-usage normalization.
- The emitter attaches `TurnUsage` to the **turn span** via `adk.tracing.span(data=...)`
  (which already accepts a `BaseModel`) and returns `TurnResult` to the caller. The same
  object can feed the OTel `LLMMetrics` and downstream metrics (e.g. the golden agent's
  per-turn DogStatsD emission), so traces and metrics share one shape.

### Surfacing `TurnUsage` from the tap

Python async generators cannot cleanly return a value to their consumer, so the tap does not
return `TurnUsage` via `StopAsyncIteration`. Instead the per-harness entry is a small object:

```
class HarnessTurn:
    events: AsyncIterator[StreamTaskMessage*]   # the canonical stream
    def usage(self) -> TurnUsage                 # populated once `events` is exhausted
```

The emitter drives `events` (delivering + tracing), then reads `usage()` to finalize the turn
span and build `TurnResult`. This keeps the canonical stream pure (only `StreamTaskMessage*`)
while giving usage/cost a typed home.

## Backwards compatibility (every change is additive)

The end state "replaces" the old converters, but it is reached additively. No public symbol
is removed in this stack; nothing regresses.

- **Taps:** existing `convert_*_to_agentex_events` keep exact signatures and output. Behavior
  is unchanged when no trace context is present.
- **Auto-send entry points** (`stream_langgraph_events(stream, task_id)`, the pydantic/openai
  `_async` helpers, `run_agent_streamed_auto_send`, `chat_completion_stream_auto_send`) keep
  signatures and return values, reimplemented to delegate to the shared auto-send adapter.
  Feature-add: they emit traces by default. The conformance suite asserts equivalent Redis
  messages before/after.
- **`_tracing.py` handlers** stay importable as shims; the shared tracer supersedes them
  internally.
- **Removal/deprecation** of dead internal duplication is the final PR, behind a deprecation
  note, never mixed into a migration PR.

## Rollout — stacked PRs (each < 1000 lines diff)

1. **Span derivation (`TracingTap`)** — pure function: canonical stream → spans.
   Unit-tested in isolation. No wiring.
2. **Auto-send adapter** — canonical stream → `adk.streaming` side effects. Fixture-tested.
   Not yet wired into harnesses.
3. **Yield adapter + `UnifiedEmitter` facade + public `adk` surface** — plus the
   conformance-test scaffold (fixture format + parametrized runner) and an empty CI
   integration job.
4. **Migrate pydantic-ai** — reimplement its `_async` / tracing on the shared components;
   keep `convert_pydantic_ai_to_agentex_events` signature; default tracing on. Add 3 test
   agents (sync / async / temporal) + CI matrix entries + live smoke.
5. **Migrate LangGraph** — same pattern + 3 test agents + CI.
6. **Migrate OpenAI Agents** — same pattern + 3 test agents + CI.
7. **claude-code parser tap** — `convert_claude_code_to_agentex_events` + recorded stream-json
   fixtures + feasible test agent(s) (likely temporal-only, given the sandbox requirement).
8. **codex parser tap** — same shape + fixtures + feasible test agent(s).
9. **Cleanup** — delete now-dead internal duplication, deprecate shims, docs.

## Testing

### Offline conformance suite (every PR)

Committed raw harness outputs (pydantic `AgentStreamEvent`s, LangGraph chunks, OpenAI stream,
claude/codex stream-json) drive a shared parametrized suite. For each fixture, assert:

- exact normalized `StreamTaskMessage*` sequence,
- derived span tree,
- **yield-vs-auto-send equivalence** — both channels produce the same logical events/spans.

Every tap must pass the shared cases: text, reasoning, single tool, tool error, multi-step,
and interleaved reasoning + tool ordering. Deterministic, offline, no network.

### Live integration matrix (CI)

Three test agents per harness, one per agent type (sync / async / temporal), deployed and
driven with a fixed prompt. Assert the unified surface produced valid ordered messages and a
well-formed span tree. Modeled on the existing `agentex-tutorials-test.yml` /
`build-and-push-tutorial-agent.yml` CI precedent.

Matrix: harness ∈ {pydantic-ai, langgraph, openai-agents, claude-code, codex} × agent-type ∈
{sync, async, temporal}. claude-code/codex run the subset of agent types that is feasible;
any uncovered cell is logged/documented, never silently skipped.

### Error handling

- A tap that raises mid-stream closes open streaming contexts and open spans — no leaked
  `adk.streaming` context, no dangling span.
- Tracing failures are best-effort and never break delivery (matches the golden agent's
  contract).

## Golden agent integration (SGP / sandbox coupling preserved)

The unified surface is designed so the golden agent keeps **all** of its SGP-coupled layers
and only swaps its hand-rolled parsing/streaming/tracing internals for the SDK's taps +
emitter. Nothing SGP-specific moves into the SDK.

What stays in the golden agent, untouched:

- Sandbox pool acquire modes (cold-create / warm-claim / reconnect), lease coordination, and
  the data-plane URL override.
- Secret resolution, OAuth/MCP reauth, and reconnect-notice emission (the notice is just
  another standalone message on the task stream, independent of the harness tap).
- Spawning `claude -p` / `codex exec` inside the sandbox.

What changes inside the golden agent's provider:

1. Acquire/provision the sandbox and resolve secrets/MCP exactly as today (SGP-coupled).
2. Spawn the CLI in the sandbox and feed its stdout (stream-json lines) into the SDK tap
   `convert_claude_code_to_agentex_events` / `convert_codex_to_agentex_events`.
3. Run that tap through the SDK emitter's **auto-send** path from inside the existing Temporal
   activity, getting streaming + tracing + `TurnUsage` for free. The agent's
   `_StreamJsonProcessor` and `AgentexStreamAdapter` are retired in favor of the SDK tap +
   emitter.

**Sandbox-setup events:** today the golden agent surfaces provisioning steps (reconnect /
find / create / configure-git / clone) as UI tool calls by yielding them into the same
adapter. Under the unified surface these become agent-produced `ToolRequestContent` /
`ToolResponseContent` messages, chained *before* the harness tap's stream into one canonical
stream for the turn (`chain(setup_events, convert_claude_code(stdout))`). The emitter then
delivers and traces the whole turn uniformly, so setup steps keep appearing in the UI and the
span tree.

This means the claude-code/codex parser PRs (7, 8) deliver the SDK taps, and a corresponding
**golden-agent-side change** (out of this repo's PR stack) rewires its providers onto them.
The golden agent's in-process litellm / OpenAI-Agents harness can likewise adopt the OpenAI
tap, though that is optional and not required by this design.

## Out of scope

- Sandbox pool, sandbox lifecycle, MCP server provisioning, and OAuth/secret reauth — tracked
  separately; only the pure claude-code/codex output parsers are in scope here.
- claude-code/codex sandbox / secret / MCP orchestration — stays in the golden agent and
  feeds the SDK parser.
