# Changelog

## Unreleased

### ⚠ BREAKING CHANGES

* **harness:** removed the deprecated bespoke LangGraph tracing handler `create_langgraph_tracing_handler` (and its `AgentexLangGraphTracingHandler` class) from the public `agentex.lib.adk` surface. Span tracing is now derived from the canonical `StreamTaskMessage*` stream by `UnifiedEmitter` — wrap your run in the harness `*Turn` and drive `UnifiedEmitter.yield_turn` / `auto_send_turn`. The `agentex init` templates were migrated accordingly.
* **harness:** removed the deprecated bespoke Pydantic-AI tracing handler `create_pydantic_ai_tracing_handler` (and its `AgentexPydanticAITracingHandler` class) from the public `agentex.lib.adk` surface. Span tracing is now derived from the canonical `StreamTaskMessage*` stream by `UnifiedEmitter` — wrap your run in `PydanticAITurn` and drive `UnifiedEmitter.yield_turn` / `auto_send_turn`. The `agentex init` templates were migrated accordingly.
* **harness:** each harness now exposes exactly `_<harness>_sync.py` + `_<harness>_turn.py` under `agentex.lib.adk._modules`. The OpenAI harness `OpenAITurn` and `convert_openai_to_agentex_events` moved to `agentex.lib.adk._modules._openai_turn` / `_openai_sync`; back-compat shims remain at `agentex.lib.adk.providers._modules.{openai_turn,sync_provider}` for one release. Public facade names (`stream_pydantic_ai_events`, `stream_langgraph_events`, `emit_langgraph_messages`, etc.) are unchanged.

### Features

* **tracing:** emit OTel metrics for async span queue depth, batch drain, and SGP export success/failure (HTTP status labels). Disable SDK-side recording with ``AGENTEX_TRACING_METRICS=0``.

## 0.18.0 (2026-07-10)

Full Changelog: [agentex-client-v0.17.0...agentex-client-v0.18.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.17.0...agentex-client-v0.18.0)

### Features

* **api:** add schedule resume ([56f41aa](https://github.com/scaleapi/scale-agentex-python/commit/56f41aa78a79ba7ff75acb909371354f6732a299))
* **api:** add skipped_action_times field to agents schedule responses ([de49d43](https://github.com/scaleapi/scale-agentex-python/commit/de49d43d6dd4fd12896c519ebd745c87f224f596))
* **api:** add webhook endpoint ([f1c1252](https://github.com/scaleapi/scale-agentex-python/commit/f1c1252edea74f7cb84deb11d5e915a1e5506ea6))
* **api:** manual updates ([e855070](https://github.com/scaleapi/scale-agentex-python/commit/e855070cc8dcb4f5ffae96f55ba8862ac890dafc))
* **api:** manual updates ([e3c8baf](https://github.com/scaleapi/scale-agentex-python/commit/e3c8baf19509319e9d5b545d95574cf92f24e63c))
* **api:** remove retrieve/delete/pause/trigger/unpause, update create/list in schedules ([8f084b6](https://github.com/scaleapi/scale-agentex-python/commit/8f084b6080cb2492ea8d18f4209547be0c057437))
* **api:** update schedule configs ([c1e7db8](https://github.com/scaleapi/scale-agentex-python/commit/c1e7db875930c532e61a8ab72ec3b62473caae3a))
* Use stable handles for run schedules ([9145865](https://github.com/scaleapi/scale-agentex-python/commit/91458652755536383693466c1b63a357bf610099))


### Bug Fixes

* cap openai &lt;2.45 for openai-agents 0.14.x compatibility ([#459](https://github.com/scaleapi/scale-agentex-python/issues/459)) ([14c124d](https://github.com/scaleapi/scale-agentex-python/commit/14c124d363ed964ed8c08e10a95ca3939095ea92))


### Chores

* **internal:** version bump ([7aeb893](https://github.com/scaleapi/scale-agentex-python/commit/7aeb8937bb794586f7d5931bdc5964d007762b4c))
* **internal:** version bump ([fcddeea](https://github.com/scaleapi/scale-agentex-python/commit/fcddeea8ef4bdff0a5f7735156c3003166464eac))
* **internal:** version bump ([0793543](https://github.com/scaleapi/scale-agentex-python/commit/079354303393c28c5087ce3907d4b5b4a64ee1c0))

## 0.17.0 (2026-07-01)

Full Changelog: [agentex-client-v0.16.2...agentex-client-v0.17.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.16.2...agentex-client-v0.17.0)

### Features

* **temporal:** opt-in continue-as-new for long-lived agent workflows ([#447](https://github.com/scaleapi/scale-agentex-python/issues/447)) ([98cf744](https://github.com/scaleapi/scale-agentex-python/commit/98cf7444002b5f9862f3a922665f016ae6c89af0))

## 0.16.2 (2026-06-29)

Full Changelog: [agentex-client-v0.16.1...agentex-client-v0.16.2](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.16.1...agentex-client-v0.16.2)

### Bug Fixes

* **adk:** release streaming buffer repair in sdk ([#449](https://github.com/scaleapi/scale-agentex-python/issues/449)) ([20795cb](https://github.com/scaleapi/scale-agentex-python/commit/20795cb158244767207b6d3758929014bc015bb6))

## 0.16.1 (2026-06-26)

Full Changelog: [agentex-client-v0.16.0...agentex-client-v0.16.1](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.16.0...agentex-client-v0.16.1)

### Bug Fixes

* **streaming:** StreamTaskMessageFull closes the coalescing buffer ([#426](https://github.com/scaleapi/scale-agentex-python/issues/426)) ([94ce668](https://github.com/scaleapi/scale-agentex-python/commit/94ce6687a86ecac8ee1a6ee1b3448f463e3b0e83))

## 0.16.0 (2026-06-24)

Full Changelog: [agentex-client-v0.15.0...agentex-client-v0.16.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.15.0...agentex-client-v0.16.0)

### ⚠ BREAKING CHANGES

* **harness:** consolidate the Pydantic-AI harness + remove tracing handler ([#431](https://github.com/scaleapi/scale-agentex-python/issues/431))
* **harness:** consolidate the LangGraph harness + remove tracing handler ([#430](https://github.com/scaleapi/scale-agentex-python/issues/430))

### Features

* **cli:** add claude-code init templates (sync / async / temporal) ([#435](https://github.com/scaleapi/scale-agentex-python/issues/435)) ([fd9bc4a](https://github.com/scaleapi/scale-agentex-python/commit/fd9bc4a81417b9d75ad692b779293720f8435d37))
* **cli:** add codex init templates (sync / async / temporal) ([#436](https://github.com/scaleapi/scale-agentex-python/issues/436)) ([0fadfd7](https://github.com/scaleapi/scale-agentex-python/commit/0fadfd7a113536d49a99894a3b80ed0915a0e0fb))
* **cli:** add default-openai-agents init template (async base) ([#434](https://github.com/scaleapi/scale-agentex-python/issues/434)) ([624e9c8](https://github.com/scaleapi/scale-agentex-python/commit/624e9c8f3b4c4288a7037bc83651970cfb02e6b0))
* **openai-agents:** single-emit + input-bearing tool spans + run_turn ([#445](https://github.com/scaleapi/scale-agentex-python/issues/445)) ([53ab8ef](https://github.com/scaleapi/scale-agentex-python/commit/53ab8efaaf65590e71abe07149582ea59814921b))
* **openai-temporal:** render hosted/server-side tool calls in TemporalStreamingModel ([#442](https://github.com/scaleapi/scale-agentex-python/issues/442)) ([5dce9f0](https://github.com/scaleapi/scale-agentex-python/commit/5dce9f097723d3436a0e40277139e7cce68580ef))


### Bug Fixes

* **cli:** harden init templates per Greptile feedback (suite-wide) ([#444](https://github.com/scaleapi/scale-agentex-python/issues/444)) ([2d85eb0](https://github.com/scaleapi/scale-agentex-python/commit/2d85eb0952f2298e6c412ab44b9c59255431cb84))
* **harness:** harden Claude Code + OpenAI taps and span tracing ([#446](https://github.com/scaleapi/scale-agentex-python/issues/446)) ([5b4359d](https://github.com/scaleapi/scale-agentex-python/commit/5b4359dcf28f390f780215ed954fa52e8cb4dd7c))


### Refactors

* **harness:** consolidate the LangGraph harness + remove tracing handler ([#430](https://github.com/scaleapi/scale-agentex-python/issues/430)) ([a3fb5ad](https://github.com/scaleapi/scale-agentex-python/commit/a3fb5ad51f6392a48cbb8324f15c9619f10244b6))
* **harness:** consolidate the Pydantic-AI harness + remove tracing handler ([#431](https://github.com/scaleapi/scale-agentex-python/issues/431)) ([48c3da8](https://github.com/scaleapi/scale-agentex-python/commit/48c3da8777ae20a9ca6d544238dccd64d6c62c2b))
* **harness:** move OpenAI harness into adk/_modules + facade export ([#432](https://github.com/scaleapi/scale-agentex-python/issues/432)) ([58bdb16](https://github.com/scaleapi/scale-agentex-python/commit/58bdb16b4b18db22188a29d5d1b31759f9d0dd4e))

## 0.15.0 (2026-06-23)

Full Changelog: [agentex-client-v0.14.0...agentex-client-v0.15.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.14.0...agentex-client-v0.15.0)

### Features

* **api:** add webhook endpoint ([37c7d9d](https://github.com/scaleapi/scale-agentex-python/commit/37c7d9d465943184ab84922ba1079b939516d534))
* **claude-code:** stream-json parser tap for the unified harness surface ([#420](https://github.com/scaleapi/scale-agentex-python/issues/420)) ([904339c](https://github.com/scaleapi/scale-agentex-python/commit/904339c21b8cd641a02d903c03d4a8730b4d7e84))
* **codex:** event-stream parser tap for the unified harness surface ([#421](https://github.com/scaleapi/scale-agentex-python/issues/421)) ([9b2b031](https://github.com/scaleapi/scale-agentex-python/commit/9b2b03144cc67bb497e0a301686207aba2629758))
* **harness:** public adk facade + docs for the unified harness surface (PR 9) ([#423](https://github.com/scaleapi/scale-agentex-python/issues/423)) ([fa60632](https://github.com/scaleapi/scale-agentex-python/commit/fa60632f9be84315a3fdc627745ae5b605994bd8))
* **harness:** unified harness surface — foundation (span derivation, delivery adapters, emitter) ([#412](https://github.com/scaleapi/scale-agentex-python/issues/412)) ([a9cacf4](https://github.com/scaleapi/scale-agentex-python/commit/a9cacf4eb71697351ee658a570636f04bbf31ad5))
* **langgraph:** migrate LangGraph harness onto unified surface ([#417](https://github.com/scaleapi/scale-agentex-python/issues/417)) ([d344228](https://github.com/scaleapi/scale-agentex-python/commit/d34422845de4b80ed69d2dccfdb0c680ef2fbca3))
* **openai-agents:** migrate onto the unified harness surface ([#416](https://github.com/scaleapi/scale-agentex-python/issues/416)) ([d10e151](https://github.com/scaleapi/scale-agentex-python/commit/d10e1510bd5da44ad5acc5cac638750122083fce))
* **pydantic-ai:** migrate onto unified harness surface (PR4) ([#415](https://github.com/scaleapi/scale-agentex-python/issues/415)) ([5ec62c2](https://github.com/scaleapi/scale-agentex-python/commit/5ec62c20781d24fc3e0b92734fcd444b1e791d70))
* **sdk:** add webhook helper for forward-route handlers ([#419](https://github.com/scaleapi/scale-agentex-python/issues/419)) ([514075d](https://github.com/scaleapi/scale-agentex-python/commit/514075de2189f33be4ade0ac84368019e55ed7ea))
* **streaming:** stream tool call argument deltas in TemporalStreamingModel ([#355](https://github.com/scaleapi/scale-agentex-python/issues/355)) ([c8de1d4](https://github.com/scaleapi/scale-agentex-python/commit/c8de1d4c9c3b5b3c16ad4aaf9644c1ba0d618757))
* **tracing:** skip Agentex span-start write by default (end-only ingest) ([#438](https://github.com/scaleapi/scale-agentex-python/issues/438)) ([10d22a2](https://github.com/scaleapi/scale-agentex-python/commit/10d22a27091c9c410ae808dab9cfce5dab3816a8))


### Bug Fixes

* **harness:** assert cross-channel (yield vs auto-send) conformance equivalence [AGX1-373] ([#414](https://github.com/scaleapi/scale-agentex-python/issues/414)) ([694960f](https://github.com/scaleapi/scale-agentex-python/commit/694960f913b8ba521d9236e876e5e00f57a3a3ff))
* **harness:** correct codex & openai reasoning stream envelopes ([#441](https://github.com/scaleapi/scale-agentex-python/issues/441)) ([1d86e8a](https://github.com/scaleapi/scale-agentex-python/commit/1d86e8a47a369814540b6e853cd20240c6098f27))
* **tests:** use relative import for assert_matches_type in webhooks test ([#440](https://github.com/scaleapi/scale-agentex-python/issues/440)) ([5954a9f](https://github.com/scaleapi/scale-agentex-python/commit/5954a9fc8c7961ef5ceb41abf3ca32e6e78590c5))
* **tracing:** fail open temporal span activities ([#437](https://github.com/scaleapi/scale-agentex-python/issues/437)) ([2d63eef](https://github.com/scaleapi/scale-agentex-python/commit/2d63eef53bdb919bb6568e04708e3b7abcb8075b))


### Refactors

* **cli:** migrate existing langgraph/pydantic-ai templates to unified surface ([#429](https://github.com/scaleapi/scale-agentex-python/issues/429)) ([ee41408](https://github.com/scaleapi/scale-agentex-python/commit/ee41408c420eba5c6b8fe8719c8ebd445dcd220c))
* **tutorials:** migrate to the unified harness surface + renumber ([#428](https://github.com/scaleapi/scale-agentex-python/issues/428)) ([ebaf617](https://github.com/scaleapi/scale-agentex-python/commit/ebaf617256c7971dde12fd7e25f02b05f2f42fca))

## 0.14.0 (2026-06-22)

Full Changelog: [agentex-client-v0.13.1...agentex-client-v0.14.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.13.1...agentex-client-v0.14.0)

### Features

* **api:** add is error to tools ([8ddd960](https://github.com/scaleapi/scale-agentex-python/commit/8ddd9604290d23ed59586a68bd6db46bf452104b))
* **compat:** runtime SDK↔backend version guard at ACP startup ([#408](https://github.com/scaleapi/scale-agentex-python/issues/408)) ([433c999](https://github.com/scaleapi/scale-agentex-python/commit/433c999bbdb4817d2048c5454cb65b54812950af))


### Bug Fixes

* **types:** add missing Optional import to ToolResponseContent ([3439f6e](https://github.com/scaleapi/scale-agentex-python/commit/3439f6edec9ab89d685b5b1c99e567a67c911522))

## 0.13.1 (2026-06-17)

Full Changelog: [agentex-client-v0.13.0...agentex-client-v0.13.1](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.13.0...agentex-client-v0.13.1)

### Bug Fixes

* **adk:** re-send task_id/agent_id in state updates for backend compatibility ([#405](https://github.com/scaleapi/scale-agentex-python/issues/405)) ([f59f26d](https://github.com/scaleapi/scale-agentex-python/commit/f59f26d4402f01318cf34d57820e121d97719986))
* **packaging:** guard agentex-client surface, bump floor, smoke-test wheel install ([#406](https://github.com/scaleapi/scale-agentex-python/issues/406)) ([a5abbb9](https://github.com/scaleapi/scale-agentex-python/commit/a5abbb9669c6ab71c52e60db72676c95c20d840d))


### Documentation

* drop stale keep_files / dashboard-config comments ([#401](https://github.com/scaleapi/scale-agentex-python/issues/401)) ([23858df](https://github.com/scaleapi/scale-agentex-python/commit/23858df775d0a617c6418eed28f1b68c9bf9ed5c))

## 0.13.0 (2026-06-10)

Full Changelog: [agentex-client-v0.12.0...agentex-client-v0.13.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-client-v0.12.0...agentex-client-v0.13.0)

### ⚠ BREAKING CHANGES

* **packaging:** release tag scheme changes from v* to <component>-v*.

### Features

* add AgentCard for self-describing agent capabilities ([#296](https://github.com/scaleapi/scale-agentex-python/issues/296)) ([6509be1](https://github.com/scaleapi/scale-agentex-python/commit/6509be1e5d9bc53e6058b22c45c760e04a4c4006))
* add HTTP-proxy LangGraph checkpointer ([19fae2f](https://github.com/scaleapi/scale-agentex-python/commit/19fae2f6e3ce4302066a403cac4c6499410ec4ad))
* add OCI Helm registry support for agent deployments ([#255](https://github.com/scaleapi/scale-agentex-python/issues/255)) ([5f054b5](https://github.com/scaleapi/scale-agentex-python/commit/5f054b514ff919479b0914883ed163279820c848))
* **adk:** allow all ClaudeAgentOptions in run_claude_agent_activity ([25bbe24](https://github.com/scaleapi/scale-agentex-python/commit/25bbe24b57feaab2e557ca15279369bfb59e02db))
* **adk:** Revamp run_claude_agent_activity to use more streaming ([#309](https://github.com/scaleapi/scale-agentex-python/issues/309)) ([0c16595](https://github.com/scaleapi/scale-agentex-python/commit/0c16595017164649bbea1bab8767010c9be7228d))
* **api:** api update ([7b1b642](https://github.com/scaleapi/scale-agentex-python/commit/7b1b642404f34ff74d866e91a5ed2d6f0a4424c6))
* **api:** api update ([710c63f](https://github.com/scaleapi/scale-agentex-python/commit/710c63f3a9b0494635c41e0d3498d69dc9145b81))
* **api:** api update ([8abce2b](https://github.com/scaleapi/scale-agentex-python/commit/8abce2ba6131732688f04bacff33da506e47c77f))
* **api:** Switch target to -client ([e741990](https://github.com/scaleapi/scale-agentex-python/commit/e74199029367ec7c626f5ea3057eb462e9f81b30))
* **lib:** Add task updates to adk ([a58747f](https://github.com/scaleapi/scale-agentex-python/commit/a58747f0d85733f32f67b06eee222a1464eb87fe))
* **openai_agents:** expose real `usage`, `response_id`, plumb `previous_response_id`, opt-in `prompt_cache_key` for stateful responses and prompt caching ([#335](https://github.com/scaleapi/scale-agentex-python/issues/335)) ([ba5d64b](https://github.com/scaleapi/scale-agentex-python/commit/ba5d64be1f959ff1a35b30e647a0a5ead21a8402))
* **packaging:** introduce slim agentex-client + heavy agentex-sdk split ([bbfb22e](https://github.com/scaleapi/scale-agentex-python/commit/bbfb22eb113dd1f3d5ddf82b4d377895f5ae5466))
* pass AGENTEX_DEPLOYMENT_ID in registration metadata ([#305](https://github.com/scaleapi/scale-agentex-python/issues/305)) ([31af8c6](https://github.com/scaleapi/scale-agentex-python/commit/31af8c6fc4aaafad57b70ded4883ced1254aeb1b))
* **tracing:** Add background queue for async span processing ([#303](https://github.com/scaleapi/scale-agentex-python/issues/303)) ([3a60add](https://github.com/scaleapi/scale-agentex-python/commit/3a60add048ff24266a45700b4e78def8ffed3e0b))


### Bug Fixes

* add litellm retry with exponential backoff for rate limit errors ([ccdb24a](https://github.com/scaleapi/scale-agentex-python/commit/ccdb24a08607298f8dafd748ee9e7fe8ba13d5fe))
* **adk:** fix to queue drain ([#327](https://github.com/scaleapi/scale-agentex-python/issues/327)) ([a862a06](https://github.com/scaleapi/scale-agentex-python/commit/a862a0646365d86acd4b0e1cf470fce522a6fbb3))
* **api:** remove agent_id and task_id parameters from states update method ([a7cbaae](https://github.com/scaleapi/scale-agentex-python/commit/a7cbaae4416e2d712623ecfac5e251c07c537958))
* **client:** preserve hardcoded query params when merging with user params ([d2c4788](https://github.com/scaleapi/scale-agentex-python/commit/d2c47883c4247a0c5a318042ff38384ddc8db4ea))
* ensure file data are only sent as 1 parameter ([48fae27](https://github.com/scaleapi/scale-agentex-python/commit/48fae27b6a761984f7fb70cb7a87da76a4192d12))
* render .env.example template in agentex init ([#351](https://github.com/scaleapi/scale-agentex-python/issues/351)) ([6092595](https://github.com/scaleapi/scale-agentex-python/commit/6092595fa8a267b2c305baba09e2682c04d593b3))
* Temporal Union deserialization causing tool_response messages to be lost ([79ef4dd](https://github.com/scaleapi/scale-agentex-python/commit/79ef4dd7a0ab1b8bb1151f5e16124ec5a947dfd4))
* **temporal:** allowing-ACP-temporal-telemetry ([9b44eb0](https://github.com/scaleapi/scale-agentex-python/commit/9b44eb0f5c6482984f972674d7a8612980c5b576))
* **tests:** repair test_streaming_model so all 28 tests run and pass ([#334](https://github.com/scaleapi/scale-agentex-python/issues/334)) ([7e5e69c](https://github.com/scaleapi/scale-agentex-python/commit/7e5e69c132c89d054516e1a762e0437375859663))
* **tracing:** Fix memory leak in SGP tracing processors ([#302](https://github.com/scaleapi/scale-agentex-python/issues/302)) ([f43dac4](https://github.com/scaleapi/scale-agentex-python/commit/f43dac4fa7ca7090b37c6c3bf285eb12515764bb))
* **tutorials:** stop at130-langgraph workflow deadlock on graph compile ([#399](https://github.com/scaleapi/scale-agentex-python/issues/399)) ([bd90a61](https://github.com/scaleapi/scale-agentex-python/commit/bd90a613958a330f1a6670f621000a9aaed1025b))


### Performance Improvements

* **client:** optimize file structure copying in multipart requests ([f5064f9](https://github.com/scaleapi/scale-agentex-python/commit/f5064f939788d72fedac91436982a8848d0f1f4f))
* **tracing:** larger span batch + linger_ms for high-volume ingest ([#397](https://github.com/scaleapi/scale-agentex-python/issues/397)) ([c0d6330](https://github.com/scaleapi/scale-agentex-python/commit/c0d633052d373daa63e8cefb9339736c0a7855fb))
* **tracing:** skip span-start upsert by default (end-only ingest) ([#394](https://github.com/scaleapi/scale-agentex-python/issues/394)) ([ae1c7ca](https://github.com/scaleapi/scale-agentex-python/commit/ae1c7caa8599f5f82492086d04caae9a6d2b7c7d))


### Chores

* **ci:** upgrade `actions/github-script` ([7c867e8](https://github.com/scaleapi/scale-agentex-python/commit/7c867e8960b51234e5e41a9b8e3129c1dada5680))
* gitignore .claude/scheduled_tasks.lock ([#400](https://github.com/scaleapi/scale-agentex-python/issues/400)) ([e186352](https://github.com/scaleapi/scale-agentex-python/commit/e1863526408451d087568676feafca033a4656c4))


### Documentation

* **api:** clarify name parameter behavior in agent task creation ([ce5af72](https://github.com/scaleapi/scale-agentex-python/commit/ce5af729cc3a0f05905d0cebfe2ef18c16d8563e))
* clarify task name is optional in adk.acp.create_task ([#392](https://github.com/scaleapi/scale-agentex-python/issues/392)) ([bd41d9b](https://github.com/scaleapi/scale-agentex-python/commit/bd41d9bb10f08a354f02f982e6507847c19d2ad9))


### Refactors

* **config:** promote deployment-config models to agentex.config.* ([#396](https://github.com/scaleapi/scale-agentex-python/issues/396)) ([9825dba](https://github.com/scaleapi/scale-agentex-python/commit/9825dba3301754e2a86632214adcc62ff97e28bd))

## 0.12.0 (2026-06-02)

Full Changelog: [v0.11.9...v0.12.0](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.9...v0.12.0)

### Features

* **api:** Bump edition to switch rye -&gt; UV ([1bd4ff7](https://github.com/scaleapi/scale-agentex-python/commit/1bd4ff7c3299ea4238cd3e36141f7e4b035967ef))


### Bug Fixes

* cap Python test matrix at 3.13 and align dev tooling versions ([#391](https://github.com/scaleapi/scale-agentex-python/issues/391)) ([729763c](https://github.com/scaleapi/scale-agentex-python/commit/729763c9652faf3a68386083d6f617dd48f642b7))

## 0.11.9 (2026-06-02)

Full Changelog: [v0.11.8...v0.11.9](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.8...v0.11.9)

### Features

* **api:** add register build api endpoint ([30c5da4](https://github.com/scaleapi/scale-agentex-python/commit/30c5da47d84ce2bfbfbb798c2f62b9552881db7d))

## 0.11.8 (2026-06-01)

Full Changelog: [v0.11.7...v0.11.8](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.7...v0.11.8)

### Features

* **cli:** add Temporal + LangGraph agent template and example ([#383](https://github.com/scaleapi/scale-agentex-python/issues/383)) ([bbc9e02](https://github.com/scaleapi/scale-agentex-python/commit/bbc9e02d2a2b063a3e509a07ffca8ca4bf459e57))
* **tracing:** OTel span queue and export telemetry (SGPINF-1863) ([#373](https://github.com/scaleapi/scale-agentex-python/issues/373)) ([6669012](https://github.com/scaleapi/scale-agentex-python/commit/6669012638481a63bdd7629582818796ca31bdf3))

## 0.11.7 (2026-06-01)

Full Changelog: [v0.11.6...v0.11.7](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.6...v0.11.7)

### Features

* **examples:** OpenAI Agents SDK local-sandbox tutorials (sync + async + temporal) ([#377](https://github.com/scaleapi/scale-agentex-python/issues/377)) ([a66d239](https://github.com/scaleapi/scale-agentex-python/commit/a66d23955fa1a98296ef4e8b09c11afe9461268a))


### Performance Improvements

* **tracing:** bounded-concurrency span export ([#374](https://github.com/scaleapi/scale-agentex-python/issues/374)) ([7b32a0d](https://github.com/scaleapi/scale-agentex-python/commit/7b32a0d826b3ed864a3bf9de256ff8da1dafb942))


### Chores

* back-merge release 0.11.6 into next ([#384](https://github.com/scaleapi/scale-agentex-python/issues/384)) ([13d3eab](https://github.com/scaleapi/scale-agentex-python/commit/13d3eab0657f1dd5a8b7ade6c7381d3230d60aff))

## 0.11.6 (2026-05-29)

Full Changelog: [v0.11.5...v0.11.6](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.5...v0.11.6)

### Features

* **api:** add cleaned_at field to task response types ([38ed338](https://github.com/scaleapi/scale-agentex-python/commit/38ed3384094f7f07f6b2482489f457fd1dc4f76d))
* **deps:** bump openai-agents to &gt;=0.14.3 for scale-sandbox oai_agents adapter ([#375](https://github.com/scaleapi/scale-agentex-python/issues/375)) ([e1b31d9](https://github.com/scaleapi/scale-agentex-python/commit/e1b31d91abadec572989b805592b788500d61994))
* **lib:** expose data_converter kwarg on AgentexWorker and Temporal client APIs ([#372](https://github.com/scaleapi/scale-agentex-python/issues/372)) ([d04624e](https://github.com/scaleapi/scale-agentex-python/commit/d04624e6899e43a0429ef2deeb84509265b9f636))


### Bug Fixes

* **tutorials:** restore tutorial CI deps after agentex-sdk 0.11.5 (pytest + debugpy) ([#379](https://github.com/scaleapi/scale-agentex-python/issues/379)) ([0a2418c](https://github.com/scaleapi/scale-agentex-python/commit/0a2418cc9f9b06e3bdc46099106e50d226412fa0))


### Performance Improvements

* **tracing:** span queue linger + per-loop httpx keepalive ([#362](https://github.com/scaleapi/scale-agentex-python/issues/362)) ([feec842](https://github.com/scaleapi/scale-agentex-python/commit/feec8426f79e9f02533451d44997717655fd33f2))


### Chores

* back-merge release 0.11.5 into next ([#381](https://github.com/scaleapi/scale-agentex-python/issues/381)) ([ab5a7d9](https://github.com/scaleapi/scale-agentex-python/commit/ab5a7d9732a56d47efad469675c7630046106ef6))
* **deps:** drop unused runtime deps and exclude tests from wheel ([#367](https://github.com/scaleapi/scale-agentex-python/issues/367)) ([f4303d1](https://github.com/scaleapi/scale-agentex-python/commit/f4303d1e7211783d19beca6554e44eb73bb29c42))


### Refactors

* **types:** promote protocol types to agentex.protocol.* ([#371](https://github.com/scaleapi/scale-agentex-python/issues/371)) ([6f1c14f](https://github.com/scaleapi/scale-agentex-python/commit/6f1c14fd61077da52038361642a9fbc4a0a56c8b))

## 0.11.5 (2026-05-29)

Full Changelog: [v0.11.4...v0.11.5](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.4...v0.11.5)

### Features

* **api:** add cleaned_at field to task response types ([38ed338](https://github.com/scaleapi/scale-agentex-python/commit/38ed3384094f7f07f6b2482489f457fd1dc4f76d))
* **deps:** bump openai-agents to &gt;=0.14.3 for scale-sandbox oai_agents adapter ([#375](https://github.com/scaleapi/scale-agentex-python/issues/375)) ([e1b31d9](https://github.com/scaleapi/scale-agentex-python/commit/e1b31d91abadec572989b805592b788500d61994))


### Performance Improvements

* **tracing:** span queue linger + per-loop httpx keepalive ([#362](https://github.com/scaleapi/scale-agentex-python/issues/362)) ([feec842](https://github.com/scaleapi/scale-agentex-python/commit/feec8426f79e9f02533451d44997717655fd33f2))


### Chores

* **deps:** drop unused runtime deps and exclude tests from wheel ([#367](https://github.com/scaleapi/scale-agentex-python/issues/367)) ([f4303d1](https://github.com/scaleapi/scale-agentex-python/commit/f4303d1e7211783d19beca6554e44eb73bb29c42))


### Refactors

* **types:** promote protocol types to agentex.protocol.* ([#371](https://github.com/scaleapi/scale-agentex-python/issues/371)) ([6f1c14f](https://github.com/scaleapi/scale-agentex-python/commit/6f1c14fd61077da52038361642a9fbc4a0a56c8b))

## 0.11.4 (2026-05-26)

Full Changelog: [v0.11.3...v0.11.4](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.3...v0.11.4)

### Chores

* **deps:** relax redis pin to support 6.x/7.x ([#363](https://github.com/scaleapi/scale-agentex-python/issues/363)) ([7817ced](https://github.com/scaleapi/scale-agentex-python/commit/7817ced90b80430a69b6f51a6841aa921a33a093))
* relax requires-python floor to &gt;= 3.11 ([#366](https://github.com/scaleapi/scale-agentex-python/issues/366)) ([a064f92](https://github.com/scaleapi/scale-agentex-python/commit/a064f928c0fac868ec1486ef49382a9baf73b5e0))

## 0.11.3 (2026-05-20)

Full Changelog: [v0.11.2...v0.11.3](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.2...v0.11.3)

### Features

* added Pydantic AI sync, async, temporal integration ([#359](https://github.com/scaleapi/scale-agentex-python/issues/359)) ([781dfe1](https://github.com/scaleapi/scale-agentex-python/commit/781dfe172373c2e01fb642b3c98af6908c98218a))
* **api:** add schedule, checkpoints, and deployment endpoints ([53b5c36](https://github.com/scaleapi/scale-agentex-python/commit/53b5c3673e54ee4b49debd049483f1a1d4b0673d))


### Bug Fixes

* resolve lint and test failures from new endpoints ([#360](https://github.com/scaleapi/scale-agentex-python/issues/360)) ([bdf129c](https://github.com/scaleapi/scale-agentex-python/commit/bdf129c8ab976ed84aa9932d5585a753280a6a34))

## 0.11.2 (2026-05-13)

Full Changelog: [v0.11.1...v0.11.2](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.1...v0.11.2)

### Bug Fixes

* **messages:** stamp agent messages with workflow.now() for monotonic ordering ([#356](https://github.com/scaleapi/scale-agentex-python/issues/356)) ([afe5265](https://github.com/scaleapi/scale-agentex-python/commit/afe526509393d7f51e4edc261211792992ffee58))

## 0.11.1 (2026-05-13)

Full Changelog: [v0.11.0...v0.11.1](https://github.com/scaleapi/scale-agentex-python/compare/v0.11.0...v0.11.1)

### ⚠ BREAKING CHANGES

* remove AgentexTracingProcessor from default tracing processors ([#349](https://github.com/scaleapi/scale-agentex-python/issues/349))

### Features

* **api:** add models for event requests, surface created_at for messages ([1998d73](https://github.com/scaleapi/scale-agentex-python/commit/1998d73741ed32f6e527d847a7c951a6f880cab9))
* **api:** api update ([da06505](https://github.com/scaleapi/scale-agentex-python/commit/da065051e22cd49f7d47facd33db5bbb50d61f6d))
* **api:** revert model additions ([a02c15b](https://github.com/scaleapi/scale-agentex-python/commit/a02c15bfe1169a84d59647d409755d7bfcc029d0))
* **internal/types:** support eagerly validating pydantic iterators ([2c528c6](https://github.com/scaleapi/scale-agentex-python/commit/2c528c6db24cb64b7fffadafe3e8c46f316f0d56))
* remove AgentexTracingProcessor from default tracing processors ([#349](https://github.com/scaleapi/scale-agentex-python/issues/349)) ([73eca7a](https://github.com/scaleapi/scale-agentex-python/commit/73eca7ad620a7e0a8bd0180b9dee02a7dde12dbb))
* **streaming:** emit OTel metrics for ttft, tps, token counts ([#347](https://github.com/scaleapi/scale-agentex-python/issues/347)) ([3bf7d1f](https://github.com/scaleapi/scale-agentex-python/commit/3bf7d1f32f95e1346cdc823e3d1f4f027635e2dd))


### Bug Fixes

* **client:** add missing f-string prefix in file type error message ([dcb1cb4](https://github.com/scaleapi/scale-agentex-python/commit/dcb1cb489bc565828c16c327c5ab6b678b13c0fa))
* render .env.example template in agentex init ([#351](https://github.com/scaleapi/scale-agentex-python/issues/351)) ([6092595](https://github.com/scaleapi/scale-agentex-python/commit/6092595fa8a267b2c305baba09e2682c04d593b3))
* **tracing:** make SGP processor stateless to stop dropping span closes ([#354](https://github.com/scaleapi/scale-agentex-python/issues/354)) ([5e9f28d](https://github.com/scaleapi/scale-agentex-python/commit/5e9f28d2f1453b3b6faf993acf9f67a6fd098952))
* wire SGP_CLIENT_BASE_URL and silence openai-agents tracer in templates ([#352](https://github.com/scaleapi/scale-agentex-python/issues/352)) ([870324e](https://github.com/scaleapi/scale-agentex-python/commit/870324e7bb87cefc20a79dc344d8603a836ca9b5))

## 0.11.0 (2026-05-07)

Full Changelog: [v0.10.5...v0.11.0](https://github.com/scaleapi/scale-agentex-python/compare/v0.10.5...v0.11.0)

### Features

* make workflow execution timeout configurable via env var ([#348](https://github.com/scaleapi/scale-agentex-python/issues/348)) ([4094708](https://github.com/scaleapi/scale-agentex-python/commit/4094708a84026aafe19eae19d022118bb26e1a72))

## 0.10.5 (2026-05-05)

Full Changelog: [v0.10.4...v0.10.5](https://github.com/scaleapi/scale-agentex-python/compare/v0.10.4...v0.10.5)

### Features

* **api:** api update ([ffaecd5](https://github.com/scaleapi/scale-agentex-python/commit/ffaecd5a94b4082f9ef38d5c89286eabf3811759))
* **openai_agents:** expose real `usage`, `response_id`, plumb `previous_response_id`, opt-in `prompt_cache_key` for stateful responses and prompt caching ([#335](https://github.com/scaleapi/scale-agentex-python/issues/335)) ([ba5d64b](https://github.com/scaleapi/scale-agentex-python/commit/ba5d64be1f959ff1a35b30e647a0a5ead21a8402))


### Chores

* **internal:** reformat pyproject.toml ([ba06702](https://github.com/scaleapi/scale-agentex-python/commit/ba06702fd362656d594f73852ad2c690383892a8))
* **internal:** reformat pyproject.toml ([3faf5d5](https://github.com/scaleapi/scale-agentex-python/commit/3faf5d5927abdc3036862d4d06e085cda0eb6cd4))
* **internal:** version bump ([168cc44](https://github.com/scaleapi/scale-agentex-python/commit/168cc44f8199015e232cd2bddf1669a08ee90778))
* **internal:** version bump ([5715828](https://github.com/scaleapi/scale-agentex-python/commit/5715828a358c20b1cc895a696d0c8d803ec71932))

## 0.10.4 (2026-05-04)

Full Changelog: [v0.10.3...v0.10.4](https://github.com/scaleapi/scale-agentex-python/compare/v0.10.3...v0.10.4)

### Features

* add service account id option for registering agentex agents ([8365771](https://github.com/scaleapi/scale-agentex-python/commit/83657710ddb95d61bb5173ca881fe602344ff495))

## 0.10.3 (2026-04-30)

Full Changelog: [v0.10.2...v0.10.3](https://github.com/scaleapi/scale-agentex-python/compare/v0.10.2...v0.10.3)

### Features

* **api:** api update ([16ab771](https://github.com/scaleapi/scale-agentex-python/commit/16ab771ab1396b94c768ec5185c2f8ed07eff556))
* **api:** api update ([fe77732](https://github.com/scaleapi/scale-agentex-python/commit/fe77732da48c872739bc6296d2932d4d9c810a35))
* support setting headers via env ([a73fd73](https://github.com/scaleapi/scale-agentex-python/commit/a73fd73ea036fc195c124636337acdc0552f18f1))


### Bug Fixes

* **adk:** Always inject headers on execute activity ([#337](https://github.com/scaleapi/scale-agentex-python/issues/337)) ([9d80e0b](https://github.com/scaleapi/scale-agentex-python/commit/9d80e0b797a9ed7a0838003294dc7a595ab18de5))
* allow litellm security patch ([#336](https://github.com/scaleapi/scale-agentex-python/issues/336)) ([c980948](https://github.com/scaleapi/scale-agentex-python/commit/c9809482d5e6095063115d1851f0b92a5e5a3755))
* **tests:** repair test_streaming_model so all 28 tests run and pass ([#334](https://github.com/scaleapi/scale-agentex-python/issues/334)) ([7e5e69c](https://github.com/scaleapi/scale-agentex-python/commit/7e5e69c132c89d054516e1a762e0437375859663))
* use correct field name format for multipart file arrays ([bd6d362](https://github.com/scaleapi/scale-agentex-python/commit/bd6d362aee81873b7969b0367488029e2bb0314b))


### Performance Improvements

* **streaming:** coalesce per-token publishes to Redis (50ms / 128-char window) ([#333](https://github.com/scaleapi/scale-agentex-python/issues/333)) ([e6f11c4](https://github.com/scaleapi/scale-agentex-python/commit/e6f11c45e6dc3186770088688ad45cc251387e4a))


### Chores

* **internal:** more robust bootstrap script ([f004301](https://github.com/scaleapi/scale-agentex-python/commit/f0043013a44ddcd9f356a8e0a548e4a295cb1b1d))

## 0.10.2 (2026-04-21)

Full Changelog: [v0.10.1...v0.10.2](https://github.com/scaleapi/scale-agentex-python/compare/v0.10.1...v0.10.2)

### Features

* **api:** api update ([d5b9945](https://github.com/scaleapi/scale-agentex-python/commit/d5b99455c248a629bb2c56a2b5daf192d9f70db8))


### Bug Fixes

* **adk:** fix to queue drain ([#327](https://github.com/scaleapi/scale-agentex-python/issues/327)) ([b59d6d8](https://github.com/scaleapi/scale-agentex-python/commit/b59d6d8b59cec9548ec468cae3827d785c9f86f7))


### Performance Improvements

* **client:** optimize file structure copying in multipart requests ([87fe899](https://github.com/scaleapi/scale-agentex-python/commit/87fe899713a2ec88f1c32b347a7d5c78124aaf56))

## 0.10.1 (2026-04-17)

Full Changelog: [v0.10.0...v0.10.1](https://github.com/scaleapi/scale-agentex-python/compare/v0.10.0...v0.10.1)

## 0.10.0 (2026-04-14)

Full Changelog: [v0.9.10...v0.10.0](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.10...v0.10.0)

### Features

* add AgentCard for self-describing agent capabilities ([#296](https://github.com/scaleapi/scale-agentex-python/issues/296)) ([6509be1](https://github.com/scaleapi/scale-agentex-python/commit/6509be1e5d9bc53e6058b22c45c760e04a4c4006))
* **api:** api update ([8abce2b](https://github.com/scaleapi/scale-agentex-python/commit/8abce2ba6131732688f04bacff33da506e47c77f))


### Bug Fixes

* ensure file data are only sent as 1 parameter ([48fae27](https://github.com/scaleapi/scale-agentex-python/commit/48fae27b6a761984f7fb70cb7a87da76a4192d12))
* Temporal Union deserialization causing tool_response messages to be lost ([79ef4dd](https://github.com/scaleapi/scale-agentex-python/commit/79ef4dd7a0ab1b8bb1151f5e16124ec5a947dfd4))
* **temporal:** allowing-ACP-temporal-telemetry ([9b44eb0](https://github.com/scaleapi/scale-agentex-python/commit/9b44eb0f5c6482984f972674d7a8612980c5b576))

## 0.9.10 (2026-04-07)

Full Changelog: [v0.9.9...v0.9.10](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.9...v0.9.10)

### Features

* **adk:** Revamp run_claude_agent_activity to use more streaming ([#309](https://github.com/scaleapi/scale-agentex-python/issues/309)) ([25069d3](https://github.com/scaleapi/scale-agentex-python/commit/25069d3dccc7534ecfba114b581878af758c3487))

## 0.9.9 (2026-04-07)

Full Changelog: [v0.9.8...v0.9.9](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.8...v0.9.9)

### Bug Fixes

* **client:** preserve hardcoded query params when merging with user params ([4a97659](https://github.com/scaleapi/scale-agentex-python/commit/4a97659b768335bc241e78d3897a9bd665ce1a25))

## 0.9.8 (2026-04-06)

Full Changelog: [v0.9.7...v0.9.8](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.7...v0.9.8)

### Features

* **adk:** allow all ClaudeAgentOptions in run_claude_agent_activity ([e41aec7](https://github.com/scaleapi/scale-agentex-python/commit/e41aec738f230070c5db1dcbf7e08abc1ef538d9))
* pass AGENTEX_DEPLOYMENT_ID in registration metadata ([#305](https://github.com/scaleapi/scale-agentex-python/issues/305)) ([31af8c6](https://github.com/scaleapi/scale-agentex-python/commit/31af8c6fc4aaafad57b70ded4883ced1254aeb1b))
* **tracing:** Add background queue for async span processing ([#303](https://github.com/scaleapi/scale-agentex-python/issues/303)) ([3a60add](https://github.com/scaleapi/scale-agentex-python/commit/3a60add048ff24266a45700b4e78def8ffed3e0b))


### Bug Fixes

* **tracing:** Fix memory leak in SGP tracing processors ([#302](https://github.com/scaleapi/scale-agentex-python/issues/302)) ([f43dac4](https://github.com/scaleapi/scale-agentex-python/commit/f43dac4fa7ca7090b37c6c3bf285eb12515764bb))

## 0.9.7 (2026-03-30)

Full Changelog: [v0.9.6...v0.9.7](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.6...v0.9.7)

### Features

* **lib:** Add task updates to adk ([ff12ae1](https://github.com/scaleapi/scale-agentex-python/commit/ff12ae199b38223c7c71b703fc8b11d5de99b0d8))

## 0.9.6 (2026-03-30)

Full Changelog: [v0.9.5...v0.9.6](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.5...v0.9.6)

### Features

* **api:** add task state update methods ([d699e24](https://github.com/scaleapi/scale-agentex-python/commit/d699e245d6c8f28034370ea6a654e11a3b78dc20))
* **api:** keep backwards compatible models ([3ec2a1e](https://github.com/scaleapi/scale-agentex-python/commit/3ec2a1e9987cd69fbcfeee8a8a6449b6825a1d49))
* **api:** use DeploymentHistory instead of DeploymentHistoryRetrieveResponse ([4c63d9c](https://github.com/scaleapi/scale-agentex-python/commit/4c63d9c340e56d7f602f77f2f1fb33b005577402))
* **internal:** implement indices array format for query and form serialization ([3bf3db1](https://github.com/scaleapi/scale-agentex-python/commit/3bf3db1f692b44ceb5f4ea39cb8c4fd0f81c01ee))


### Bug Fixes

* **deps:** bump minimum typing-extensions version ([fd76bc9](https://github.com/scaleapi/scale-agentex-python/commit/fd76bc994dca633c4966967c132323985eafa642))
* **pydantic:** do not pass `by_alias` unless set ([235636b](https://github.com/scaleapi/scale-agentex-python/commit/235636b424dd4595f1510a87e6b79f3b2e103c97))
* sanitize endpoint path params ([e6472be](https://github.com/scaleapi/scale-agentex-python/commit/e6472bea7d34a72d070079441b359bef25e87830))


### Chores

* **ci:** skip lint on metadata-only changes ([f4d5053](https://github.com/scaleapi/scale-agentex-python/commit/f4d5053766e5864338229218f2402d60f431d1fa))
* **ci:** skip uploading artifacts on stainless-internal branches ([45e7622](https://github.com/scaleapi/scale-agentex-python/commit/45e76227d8b0d5d1c2f398e9945b71eb5953e791))
* format all `api.md` files ([e67fa69](https://github.com/scaleapi/scale-agentex-python/commit/e67fa69c072f462ea86ecd67b888afa5f97cc7cc))
* **internal:** add request options to SSE classes ([b788da0](https://github.com/scaleapi/scale-agentex-python/commit/b788da0d1b9fb6100dffb4a99b761ddcb7f0160e))
* **internal:** bump dependencies ([95112dd](https://github.com/scaleapi/scale-agentex-python/commit/95112dd25a3bf8a49bd1080bfddefd403e64cfcb))
* **internal:** fix lint error on Python 3.14 ([cb99db1](https://github.com/scaleapi/scale-agentex-python/commit/cb99db1857e373c3dc47d4f5ff6861d06b0ddce4))
* **internal:** make `test_proxy_environment_variables` more resilient ([7bfaa75](https://github.com/scaleapi/scale-agentex-python/commit/7bfaa75be00bf8f11030f42a3dc6fdcd980c5823))
* **internal:** make `test_proxy_environment_variables` more resilient to env ([fd1a06e](https://github.com/scaleapi/scale-agentex-python/commit/fd1a06e212cf1a314ac7c61e4d51879401e120f9))
* **internal:** remove mock server code ([3a5ae0f](https://github.com/scaleapi/scale-agentex-python/commit/3a5ae0f0451610ae56284307d4c2bee1ac2964c1))
* **internal:** tweak CI branches ([2e74af0](https://github.com/scaleapi/scale-agentex-python/commit/2e74af08e3e2dd4179550e9dd1cf22881195ac91))
* **internal:** update gitignore ([aba7c4f](https://github.com/scaleapi/scale-agentex-python/commit/aba7c4f8264fdad515a4926884f855c2d87aa910))
* **internal:** version bump ([1ef69ed](https://github.com/scaleapi/scale-agentex-python/commit/1ef69ed5415d3112055a8040eccfb6eca452e532))
* **internal:** version bump ([1132255](https://github.com/scaleapi/scale-agentex-python/commit/1132255a0cd7aec1daed38e4110cd6bac53f930a))
* **internal:** version bump ([60e5402](https://github.com/scaleapi/scale-agentex-python/commit/60e5402c4502957aee7848ab3cdcbfb41503a8ae))
* update mock server docs ([8c5c6d3](https://github.com/scaleapi/scale-agentex-python/commit/8c5c6d38214b13f645f6fbd75efbbb8116458589))

## 0.9.5 (2026-03-24)

Full Changelog: [v0.9.4...v0.9.5](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.4...v0.9.5)

## 0.9.4 (2026-02-18)

Full Changelog: [v0.9.3...v0.9.4](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.3...v0.9.4)

## 0.9.3 (2026-02-13)

Full Changelog: [v0.9.2...v0.9.3](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.2...v0.9.3)

### Features

* add HTTP-proxy LangGraph checkpointer ([19fae2f](https://github.com/scaleapi/scale-agentex-python/commit/19fae2f6e3ce4302066a403cac4c6499410ec4ad))
* add OCI Helm registry support for agent deployments ([#255](https://github.com/scaleapi/scale-agentex-python/issues/255)) ([5f054b5](https://github.com/scaleapi/scale-agentex-python/commit/5f054b514ff919479b0914883ed163279820c848))

## 0.9.2 (2026-02-06)

Full Changelog: [v0.9.1...v0.9.2](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.1...v0.9.2)

### Features

* **client:** add custom JSON encoder for extended type support ([a0720ab](https://github.com/scaleapi/scale-agentex-python/commit/a0720abb088583ce4b596e464f7483a4be728e29))


### Bug Fixes

* add litellm retry with exponential backoff for rate limit errors ([ccdb24a](https://github.com/scaleapi/scale-agentex-python/commit/ccdb24a08607298f8dafd748ee9e7fe8ba13d5fe))

## 0.9.1 (2026-01-26)

Full Changelog: [v0.9.0...v0.9.1](https://github.com/scaleapi/scale-agentex-python/compare/v0.9.0...v0.9.1)

### Chores

* **ci:** upgrade `actions/github-script` ([71d5c6c](https://github.com/scaleapi/scale-agentex-python/commit/71d5c6c67362f18e0cbdc27cca37672778ff6b1f))

## 0.9.0 (2026-01-21)

Full Changelog: [v0.8.2...v0.9.0](https://github.com/scaleapi/scale-agentex-python/compare/v0.8.2...v0.9.0)

### Features

* **api:** api update ([33ade28](https://github.com/scaleapi/scale-agentex-python/commit/33ade2859c35413ecb4972a68a85cc0ef426e864))
* **client:** add support for binary request streaming ([07e2881](https://github.com/scaleapi/scale-agentex-python/commit/07e2881a23ad2c624306c8d10ab661ddef42deec))


### Chores

* **internal:** update `actions/checkout` version ([64d91f6](https://github.com/scaleapi/scale-agentex-python/commit/64d91f6984c577e0a8a1546bc0f96f944d343a7d))

## 0.8.2 (2026-01-02)

Full Changelog: [v0.8.1...v0.8.2](https://github.com/scaleapi/scale-agentex-python/compare/v0.8.1...v0.8.2)

### Features

* **api:** api update ([f2115eb](https://github.com/scaleapi/scale-agentex-python/commit/f2115ebf273043a87ea50b39837138bfc30a63d6))

## 0.8.1 (2025-12-22)

Full Changelog: [v0.8.0...v0.8.1](https://github.com/scaleapi/scale-agentex-python/compare/v0.8.0...v0.8.1)

### Features

* **api:** add messages/paginated endpoint ([3e03aff](https://github.com/scaleapi/scale-agentex-python/commit/3e03aff8490e0556cb05052d385156eda8f28107))
* **api:** add messages/paginated to stainless config ([2473ded](https://github.com/scaleapi/scale-agentex-python/commit/2473ded39274bcd0a16d7314667fcf7f55e829c2))
* **api:** api update ([2e4ec2f](https://github.com/scaleapi/scale-agentex-python/commit/2e4ec2f28413ee58afa664b793565d6be4da5dfe))
* **api:** api update ([ed21ad8](https://github.com/scaleapi/scale-agentex-python/commit/ed21ad8c34cd11e80af9128181764489a0541740))
* **api:** api update ([86a166a](https://github.com/scaleapi/scale-agentex-python/commit/86a166aba5538411ebcc0ed74291505e01a466f2))
* **api:** api update ([4c95c94](https://github.com/scaleapi/scale-agentex-python/commit/4c95c94df570277fc49281f1343cb012e8da2334))
* **api:** api update ([f6eccdf](https://github.com/scaleapi/scale-agentex-python/commit/f6eccdf975eaef9b257ef3f20f087f2f2f9b3665))
* **api:** api update ([41067fb](https://github.com/scaleapi/scale-agentex-python/commit/41067fb79725787e0ceb20dcf16029998bcbca24))
* **api:** api update ([cdc9c63](https://github.com/scaleapi/scale-agentex-python/commit/cdc9c636be6f26e84772d1d1ef9d47cddcd9dabc))
* **api:** api update ([413d9c8](https://github.com/scaleapi/scale-agentex-python/commit/413d9c806d918d7c5da3d0249c0f11d4b9f0894e))
* **api:** api update ([1b4bf7d](https://github.com/scaleapi/scale-agentex-python/commit/1b4bf7d3a11306a50ec0eb9c20764c585d0e98e4))
* **api:** manual updates ([131e836](https://github.com/scaleapi/scale-agentex-python/commit/131e836b5bda8248f847b00308b6711a1ee84ee0))
* **api:** update via SDK Studio ([2a6c7fa](https://github.com/scaleapi/scale-agentex-python/commit/2a6c7fa919ad255f9e53e7f97f195065599a05e9))


### Bug Fixes

* ensure streams are always closed ([7bb9db8](https://github.com/scaleapi/scale-agentex-python/commit/7bb9db851a213d261e585cd2f156046f05cf85db))
* **types:** allow pyright to infer TypedDict types within SequenceNotStr ([9cfc9d6](https://github.com/scaleapi/scale-agentex-python/commit/9cfc9d66579a11f3eaf248bafbfddb422e878a58))
* use async_to_httpx_files in patch method ([8abb539](https://github.com/scaleapi/scale-agentex-python/commit/8abb539a340af3a2a42482757412c0c408817461))


### Chores

* add missing docstrings ([81f1fa9](https://github.com/scaleapi/scale-agentex-python/commit/81f1fa9b3c440d893b8ea8f773ab2592eb333d65))
* **deps:** mypy 1.18.1 has a regression, pin to 1.17 ([e20aaa4](https://github.com/scaleapi/scale-agentex-python/commit/e20aaa495384f547dd18c8d31496f70b4a37e0dd))
* **docs:** use environment variables for authentication in code snippets ([a30f6ae](https://github.com/scaleapi/scale-agentex-python/commit/a30f6aebca8de5be72eb7bcf7a3b3ccea28479bc))
* **internal:** add `--fix` argument to lint script ([0ef4242](https://github.com/scaleapi/scale-agentex-python/commit/0ef4242888cc6ed341536e1ab1fbf6b03c723de9))
* **internal:** add missing files argument to base client ([28d1738](https://github.com/scaleapi/scale-agentex-python/commit/28d1738d3af8feb00f6f641e159221fb41c42983))
* speedup initial import ([8e50946](https://github.com/scaleapi/scale-agentex-python/commit/8e50946321c32e42a7b25cf9ae8b8e9b020a7ac9))
* update lockfile ([a3a2e4f](https://github.com/scaleapi/scale-agentex-python/commit/a3a2e4fbcf6e6e4bcbadab50c6b9236e4514dae2))

## 0.8.0 (2025-12-17)

Full Changelog: [v0.7.4...v0.8.0](https://github.com/scaleapi/scale-agentex-python/compare/v0.7.4...v0.8.0)

### Features

* **api:** api update ([2e4ec2f](https://github.com/scaleapi/scale-agentex-python/commit/2e4ec2f28413ee58afa664b793565d6be4da5dfe))


### Bug Fixes

* use async_to_httpx_files in patch method ([8abb539](https://github.com/scaleapi/scale-agentex-python/commit/8abb539a340af3a2a42482757412c0c408817461))

## 0.7.4 (2025-12-17)

Full Changelog: [v0.7.3...v0.7.4](https://github.com/scaleapi/scale-agentex-python/compare/v0.7.3...v0.7.4)

### Features

* **api:** api update ([ed21ad8](https://github.com/scaleapi/scale-agentex-python/commit/ed21ad8c34cd11e80af9128181764489a0541740))
* **api:** api update ([86a166a](https://github.com/scaleapi/scale-agentex-python/commit/86a166aba5538411ebcc0ed74291505e01a466f2))
* **api:** api update ([4c95c94](https://github.com/scaleapi/scale-agentex-python/commit/4c95c94df570277fc49281f1343cb012e8da2334))


### Chores

* **internal:** add missing files argument to base client ([28d1738](https://github.com/scaleapi/scale-agentex-python/commit/28d1738d3af8feb00f6f641e159221fb41c42983))
* speedup initial import ([8e50946](https://github.com/scaleapi/scale-agentex-python/commit/8e50946321c32e42a7b25cf9ae8b8e9b020a7ac9))

## 0.7.3 (2025-12-10)

Full Changelog: [v0.7.2...v0.7.3](https://github.com/scaleapi/scale-agentex-python/compare/v0.7.2...v0.7.3)

## 0.7.2 (2025-12-10)

Full Changelog: [v0.7.1...v0.7.2](https://github.com/scaleapi/scale-agentex-python/compare/v0.7.1...v0.7.2)

## 0.7.1 (2025-12-09)

Full Changelog: [v0.7.0...v0.7.1](https://github.com/scaleapi/scale-agentex-python/compare/v0.7.0...v0.7.1)

### Features

* **api:** api update ([92b2710](https://github.com/scaleapi/scale-agentex-python/commit/92b2710e0f060a8d59f8d8237c3ca7b8e923867a))

## 0.7.0 (2025-12-09)

Full Changelog: [v0.6.7...v0.7.0](https://github.com/scaleapi/scale-agentex-python/compare/v0.6.7...v0.7.0)

### Features

* **api:** add messages/paginated endpoint ([3e03aff](https://github.com/scaleapi/scale-agentex-python/commit/3e03aff8490e0556cb05052d385156eda8f28107))
* **api:** add messages/paginated to stainless config ([2473ded](https://github.com/scaleapi/scale-agentex-python/commit/2473ded39274bcd0a16d7314667fcf7f55e829c2))
* **api:** api update ([f6eccdf](https://github.com/scaleapi/scale-agentex-python/commit/f6eccdf975eaef9b257ef3f20f087f2f2f9b3665))
* **api:** api update ([41067fb](https://github.com/scaleapi/scale-agentex-python/commit/41067fb79725787e0ceb20dcf16029998bcbca24))
* **api:** api update ([cdc9c63](https://github.com/scaleapi/scale-agentex-python/commit/cdc9c636be6f26e84772d1d1ef9d47cddcd9dabc))
* **api:** api update ([413d9c8](https://github.com/scaleapi/scale-agentex-python/commit/413d9c806d918d7c5da3d0249c0f11d4b9f0894e))
* **api:** api update ([1b4bf7d](https://github.com/scaleapi/scale-agentex-python/commit/1b4bf7d3a11306a50ec0eb9c20764c585d0e98e4))
* **api:** manual updates ([131e836](https://github.com/scaleapi/scale-agentex-python/commit/131e836b5bda8248f847b00308b6711a1ee84ee0))


### Bug Fixes

* ensure streams are always closed ([7bb9db8](https://github.com/scaleapi/scale-agentex-python/commit/7bb9db851a213d261e585cd2f156046f05cf85db))
* **types:** allow pyright to infer TypedDict types within SequenceNotStr ([9cfc9d6](https://github.com/scaleapi/scale-agentex-python/commit/9cfc9d66579a11f3eaf248bafbfddb422e878a58))


### Chores

* add missing docstrings ([81f1fa9](https://github.com/scaleapi/scale-agentex-python/commit/81f1fa9b3c440d893b8ea8f773ab2592eb333d65))
* **deps:** mypy 1.18.1 has a regression, pin to 1.17 ([e20aaa4](https://github.com/scaleapi/scale-agentex-python/commit/e20aaa495384f547dd18c8d31496f70b4a37e0dd))
* **docs:** use environment variables for authentication in code snippets ([a30f6ae](https://github.com/scaleapi/scale-agentex-python/commit/a30f6aebca8de5be72eb7bcf7a3b3ccea28479bc))
* update lockfile ([a3a2e4f](https://github.com/scaleapi/scale-agentex-python/commit/a3a2e4fbcf6e6e4bcbadab50c6b9236e4514dae2))

## 0.6.7 (2025-11-19)

Full Changelog: [v0.6.6...v0.6.7](https://github.com/scaleapi/scale-agentex-python/compare/v0.6.6...v0.6.7)

## 0.6.6 (2025-11-12)

Full Changelog: [v0.6.5...v0.6.6](https://github.com/scaleapi/scale-agentex-python/compare/v0.6.5...v0.6.6)

### Bug Fixes

* compat with Python 3.14 ([9a62f23](https://github.com/scaleapi/scale-agentex-python/commit/9a62f23376ef797bafe67f61552eb7635286caa3))
* **compat:** update signatures of `model_dump` and `model_dump_json` for Pydantic v1 ([cf857f9](https://github.com/scaleapi/scale-agentex-python/commit/cf857f9191f10a971e9cba2a8c764229ed4a7dfe))


### Chores

* **internal:** restore stats ([5ec0383](https://github.com/scaleapi/scale-agentex-python/commit/5ec0383d9d6a85b342263ba49b8e3893924c59fc))
* **package:** drop Python 3.8 support ([3d4dc37](https://github.com/scaleapi/scale-agentex-python/commit/3d4dc37f87b8d8f1debbe6505746342e461772ba))

## 0.6.5 (2025-11-06)

Full Changelog: [v0.6.4...v0.6.5](https://github.com/scaleapi/scale-agentex-python/compare/v0.6.4...v0.6.5)

## 0.6.4 (2025-11-06)

Full Changelog: [v0.6.3...v0.6.4](https://github.com/scaleapi/scale-agentex-python/compare/v0.6.3...v0.6.4)

## 0.6.3 (2025-11-06)

Full Changelog: [v0.6.2...v0.6.3](https://github.com/scaleapi/scale-agentex-python/compare/v0.6.2...v0.6.3)

## 0.6.2 (2025-11-05)

Full Changelog: [v0.6.1...v0.6.2](https://github.com/scaleapi/scale-agentex-python/compare/v0.6.1...v0.6.2)

### Features

* **api:** update via SDK Studio ([b732dfa](https://github.com/scaleapi/scale-agentex-python/commit/b732dfac50cacc90c84a751fd6c75d18fa5b43ed))

## 0.6.1 (2025-11-05)

Full Changelog: [v0.6.0...v0.6.1](https://github.com/scaleapi/scale-agentex-python/compare/v0.6.0...v0.6.1)

### Features

* **api:** api update ([f6189a4](https://github.com/scaleapi/scale-agentex-python/commit/f6189a43e1430fdd16c8d10e6ad835d9dfa5871c))
* **api:** api update ([714c719](https://github.com/scaleapi/scale-agentex-python/commit/714c7194e488e6070c99e200b91189f50dcdb831))

## 0.6.0 (2025-11-04)

Full Changelog: [v0.5.3...v0.6.0](https://github.com/scaleapi/scale-agentex-python/compare/v0.5.3...v0.6.0)

### Features

* **api:** api update ([ec61dd3](https://github.com/scaleapi/scale-agentex-python/commit/ec61dd3124fbf169dcdcced262a30bfbed080b5f))


### Chores

* **internal:** grammar fix (it's -&gt; its) ([36e27da](https://github.com/scaleapi/scale-agentex-python/commit/36e27daed52435b300f090ac4643cd502a817a1e))

## 0.5.3 (2025-10-31)

Full Changelog: [v0.5.2...v0.5.3](https://github.com/scaleapi/scale-agentex-python/compare/v0.5.2...v0.5.3)

### Chores

* re apply example updates ([043973b](https://github.com/scaleapi/scale-agentex-python/commit/043973bec649ab2304eff7a313938e1e3e5377e5))

## 0.5.2 (2025-10-31)

Full Changelog: [v0.5.0...v0.5.2](https://github.com/scaleapi/scale-agentex-python/compare/v0.5.0...v0.5.2)

### Features

* **api:** manual updates ([dc66b57](https://github.com/scaleapi/scale-agentex-python/commit/dc66b57618525669b3aa15676343ef542675a5f9))
* bump the helm chart version ([1ffafb0](https://github.com/scaleapi/scale-agentex-python/commit/1ffafb0406138d6abd84254fa394b88c4a28ce70))


### Chores

* sync repo ([0e05416](https://github.com/scaleapi/scale-agentex-python/commit/0e05416219ca93ae347e6175804bc0f2259a6b44))

## 0.5.0 (2025-10-28)

Full Changelog: [v0.4.28...v0.5.0](https://github.com/scaleapi/agentex-python/compare/v0.4.28...v0.5.0)

### Features

* **api:** api update ([129fae6](https://github.com/scaleapi/agentex-python/commit/129fae69844e655b5dd02b6f67c44d15f5dbfa93))

## 0.4.28 (2025-10-28)

Full Changelog: [v0.4.27...v0.4.28](https://github.com/scaleapi/agentex-python/compare/v0.4.27...v0.4.28)

## 0.4.27 (2025-10-27)

Full Changelog: [v0.4.26...v0.4.27](https://github.com/scaleapi/agentex-python/compare/v0.4.26...v0.4.27)

### Features

* **api:** api update ([f5e4fd2](https://github.com/scaleapi/agentex-python/commit/f5e4fd2f2fbb2c7e67e51795fba1f0b2e13048de))

## 0.4.26 (2025-10-21)

Full Changelog: [v0.4.25...v0.4.26](https://github.com/scaleapi/agentex-python/compare/v0.4.25...v0.4.26)

### Features

* **api:** api update ([0c1dedd](https://github.com/scaleapi/agentex-python/commit/0c1dedd0fecb05e3684f110cc589f2abe55acb97))
* **api:** api update ([719dc74](https://github.com/scaleapi/agentex-python/commit/719dc74f7844e2a3c14e46996e353d9c632b8e0a))


### Chores

* bump `httpx-aiohttp` version to 0.1.9 ([21c7921](https://github.com/scaleapi/agentex-python/commit/21c79210a0d65944fec5010fcc581a2d85fb94ab))

## 0.4.25 (2025-10-10)

Full Changelog: [v0.4.24...v0.4.25](https://github.com/scaleapi/agentex-python/compare/v0.4.24...v0.4.25)

## 0.4.24 (2025-10-10)

Full Changelog: [v0.4.23...v0.4.24](https://github.com/scaleapi/agentex-python/compare/v0.4.23...v0.4.24)

### Features

* **api:** manual updates ([09996ea](https://github.com/scaleapi/agentex-python/commit/09996ea688a7225670bdd9d944b64801fac7acce))


### Bug Fixes

* health check port handling ([#138](https://github.com/scaleapi/agentex-python/issues/138)) ([fe22301](https://github.com/scaleapi/agentex-python/commit/fe223012db49768f38c4de56b5d5744031b631d1))


### Chores

* do not install brew dependencies in ./scripts/bootstrap by default ([2675e14](https://github.com/scaleapi/agentex-python/commit/2675e14bf9f3a0113a849caf2283376c448f9d03))
* improve example values ([6997fe5](https://github.com/scaleapi/agentex-python/commit/6997fe57910ea54d6d71b25fdea4497925c8ec63))
* **internal:** detect missing future annotations with ruff ([f1aa71f](https://github.com/scaleapi/agentex-python/commit/f1aa71f89bb0e8369e6d895b5111dc15fd1e2c12))
* **internal:** update pydantic dependency ([156ea64](https://github.com/scaleapi/agentex-python/commit/156ea64a4fa317d3ab483e7b9b6ba63471b618ef))
* **internal:** version bump ([8567752](https://github.com/scaleapi/agentex-python/commit/85677527f5c8d393f0eea0a2a629da48fb56f4a9))
* **internal:** version bump ([45206dd](https://github.com/scaleapi/agentex-python/commit/45206dd28643403800c386b75e1c9a442c8978ae))
* **internal:** version bump ([98354ba](https://github.com/scaleapi/agentex-python/commit/98354ba2e7630798e25a8e278cba44c1aacc1e08))
* **internal:** version bump ([aa2a8db](https://github.com/scaleapi/agentex-python/commit/aa2a8db5907f78b4b39849a1900dae27412359bb))
* **internal:** version bump ([73bba2a](https://github.com/scaleapi/agentex-python/commit/73bba2a59e77fa31caab5b668781b71bc7c5ec2d))
* **types:** change optional parameter type from NotGiven to Omit ([2117d77](https://github.com/scaleapi/agentex-python/commit/2117d77219da097e784d5d2deab1632a2855dae9))

## 0.4.23 (2025-10-02)

Full Changelog: [v0.4.22...v0.4.23](https://github.com/scaleapi/agentex-python/compare/v0.4.22...v0.4.23)

### Features

* Adding Agent info to SGP tracing metadata ([#85](https://github.com/scaleapi/agentex-python/issues/85)) ([900f66b](https://github.com/scaleapi/agentex-python/commit/900f66b60bc61ac515a7e43172d573a31c623fa9))

## 0.4.22 (2025-10-01)

Full Changelog: [v0.4.21...v0.4.22](https://github.com/scaleapi/agentex-python/compare/v0.4.21...v0.4.22)

## 0.4.21 (2025-10-01)

Full Changelog: [v0.4.20...v0.4.21](https://github.com/scaleapi/agentex-python/compare/v0.4.20...v0.4.21)

## 0.4.20 (2025-10-01)

Full Changelog: [v0.4.19...v0.4.20](https://github.com/scaleapi/agentex-python/compare/v0.4.19...v0.4.20)

## 0.4.19 (2025-10-01)

Full Changelog: [v0.4.18...v0.4.19](https://github.com/scaleapi/agentex-python/compare/v0.4.18...v0.4.19)

### Features

* Adds helm config to Agent Environment ([#125](https://github.com/scaleapi/agentex-python/issues/125)) ([e4b39b5](https://github.com/scaleapi/agentex-python/commit/e4b39b5f319452bbc6650a7ef41b3a3179bb3b93))

## 0.4.18 (2025-09-29)

Full Changelog: [v0.4.17...v0.4.18](https://github.com/scaleapi/agentex-python/compare/v0.4.17...v0.4.18)

### Chores

* **internal:** version bump ([eded756](https://github.com/scaleapi/agentex-python/commit/eded756bde2f3b4cfcf02c7a9cf72e70a82dd9aa))

## 0.4.17 (2025-09-29)

Full Changelog: [v0.4.16...v0.4.17](https://github.com/scaleapi/agentex-python/compare/v0.4.16...v0.4.17)

## 0.4.16 (2025-09-16)

Full Changelog: [v0.4.15...v0.4.16](https://github.com/scaleapi/agentex-python/compare/v0.4.15...v0.4.16)

## 0.4.15 (2025-09-16)

Full Changelog: [v0.4.14...v0.4.15](https://github.com/scaleapi/agentex-python/compare/v0.4.14...v0.4.15)

## 0.4.14 (2025-09-16)

Full Changelog: [v0.4.13...v0.4.14](https://github.com/scaleapi/agentex-python/compare/v0.4.13...v0.4.14)

### Features

* add previous_response_id parameter to OpenAI module ([7a78844](https://github.com/scaleapi/agentex-python/commit/7a78844f9efbfac606c7e52d1f469db0728c9e56))

## 0.4.13 (2025-09-12)

Full Changelog: [v0.4.12...v0.4.13](https://github.com/scaleapi/agentex-python/compare/v0.4.12...v0.4.13)

### Features

* **api:** api update ([0102183](https://github.com/scaleapi/agentex-python/commit/0102183a8f5a23dbdaf905ffbe7ffbcf59bf7b21))
* **api:** api update ([8a6edb1](https://github.com/scaleapi/agentex-python/commit/8a6edb13046ca24bf6c45fc018e32de498d48869))

## 0.4.12 (2025-09-08)

Full Changelog: [v0.4.11...v0.4.12](https://github.com/scaleapi/agentex-python/compare/v0.4.11...v0.4.12)

### ⚠ BREAKING CHANGES

* task_cancel now requires explicit agent_name/agent_id parameter to identify which agent owns the task being cancelled

### Bug Fixes

* task cancellation architectural bug ([f9a72a9](https://github.com/scaleapi/agentex-python/commit/f9a72a94f96afe86d3cc80f4f85ea368279d4517))

## 0.4.11 (2025-09-04)

Full Changelog: [v0.4.10...v0.4.11](https://github.com/scaleapi/agentex-python/compare/v0.4.10...v0.4.11)

### Features

* Guardrail support ([e3e9bf9](https://github.com/scaleapi/agentex-python/commit/e3e9bf9dd6cf16b9a783638690d4a31914be8139))
* improve future compat with pydantic v3 ([f0d8624](https://github.com/scaleapi/agentex-python/commit/f0d86244065c88bb2777db8fabeb1921e7e01116))
* multiple guardrails ([ea8f98a](https://github.com/scaleapi/agentex-python/commit/ea8f98a973ba486e854cf14528a88eb73a203cf8))
* **templates:** add custom activity timeout guidance for temporal agents ([7658256](https://github.com/scaleapi/agentex-python/commit/765825680132677ea0351f2a9410f472ee754906))
* **types:** replace List[str] with SequenceNotStr in params ([f319781](https://github.com/scaleapi/agentex-python/commit/f3197818637574cd92b2c1f710679155eddf5af7))


### Bug Fixes

* Adding new example for guardrails instead of using 10_async ([15dc44b](https://github.com/scaleapi/agentex-python/commit/15dc44b333a977564c9974cc089d5ef578840714))
* avoid newer type syntax ([6b5c82a](https://github.com/scaleapi/agentex-python/commit/6b5c82aab9ebcf755575b641aced2b77a13a71c3))


### Chores

* **internal:** add Sequence related utils ([496034d](https://github.com/scaleapi/agentex-python/commit/496034db4d6cba361c1f392a4bb86f6ab057e878))
* **internal:** change ci workflow machines ([7445d94](https://github.com/scaleapi/agentex-python/commit/7445d94cb860f92911ec97ecd951149557956c6a))
* **internal:** move mypy configurations to `pyproject.toml` file ([e96cd34](https://github.com/scaleapi/agentex-python/commit/e96cd34629d5ea173446c3184fbfe28bd2b370a0))
* **internal:** update pyright exclude list ([d952430](https://github.com/scaleapi/agentex-python/commit/d952430ab4cbc41bca06010bbcfea3eeb022073e))

## 0.4.10 (2025-08-24)

Full Changelog: [v0.4.9...v0.4.10](https://github.com/scaleapi/agentex-python/compare/v0.4.9...v0.4.10)

## 0.4.9 (2025-08-22)

Full Changelog: [v0.4.8...v0.4.9](https://github.com/scaleapi/agentex-python/compare/v0.4.8...v0.4.9)

## 0.4.8 (2025-08-22)

Full Changelog: [v0.4.7...v0.4.8](https://github.com/scaleapi/agentex-python/compare/v0.4.7...v0.4.8)

## 0.4.7 (2025-08-22)

Full Changelog: [v0.4.6...v0.4.7](https://github.com/scaleapi/agentex-python/compare/v0.4.6...v0.4.7)

### Chores

* update github action ([677e95d](https://github.com/scaleapi/agentex-python/commit/677e95de075b7031cfc4971d7d09769daaa5b2af))

## 0.4.6 (2025-08-20)

Full Changelog: [v0.4.5...v0.4.6](https://github.com/scaleapi/agentex-python/compare/v0.4.5...v0.4.6)

### Features

* **api:** api update ([7b4c80a](https://github.com/scaleapi/agentex-python/commit/7b4c80acb502c29df63a3d66a1b29b653d2e3cf5))


### Chores

* generate release ([0836e4a](https://github.com/scaleapi/agentex-python/commit/0836e4a632e8f3aa0cd05fc6b61581f8c8be9bcd))

## 0.4.5 (2025-08-20)

Full Changelog: [v0.4.4...v0.4.5](https://github.com/scaleapi/agentex-python/compare/v0.4.4...v0.4.5)

### Features

* **api:** manual updates ([34a53aa](https://github.com/scaleapi/agentex-python/commit/34a53aa28b8f862d74dd1603d92b7dd5dd28ddb1))


### Bug Fixes

* enable FunctionTool serialization for Temporal worker nodes ([c9eb040](https://github.com/scaleapi/agentex-python/commit/c9eb04002825195187cd58f34c9185349a63566e))
* **tools:** handle callable objects in model serialization to facilitate tool calling ([4e9bb87](https://github.com/scaleapi/agentex-python/commit/4e9bb87d7faa2c2e1643893a168f7c6affd2809d))


### Chores

* demonstrate FunctionTool use in a (temporal) tutorial ([3a72043](https://github.com/scaleapi/agentex-python/commit/3a7204333c328fab8ba0f1d31fd26994ea176ecf))

## 0.4.4 (2025-08-17)

Full Changelog: [v0.4.3...v0.4.4](https://github.com/scaleapi/agentex-python/compare/v0.4.3...v0.4.4)

## 0.4.3 (2025-08-17)

Full Changelog: [v0.4.2...v0.4.3](https://github.com/scaleapi/agentex-python/compare/v0.4.2...v0.4.3)

## 0.4.2 (2025-08-17)

Full Changelog: [v0.4.1...v0.4.2](https://github.com/scaleapi/agentex-python/compare/v0.4.1...v0.4.2)

## 0.4.1 (2025-08-16)

Full Changelog: [v0.4.0...v0.4.1](https://github.com/scaleapi/agentex-python/compare/v0.4.0...v0.4.1)

## 0.4.0 (2025-08-15)

Full Changelog: [v0.3.0...v0.4.0](https://github.com/scaleapi/agentex-python/compare/v0.3.0...v0.4.0)

### Features

* **api:** manual updates ([ce2a201](https://github.com/scaleapi/agentex-python/commit/ce2a201227ff6659874672fc7c6a890f25dfaa08))
* **api:** manual updates ([7afbafd](https://github.com/scaleapi/agentex-python/commit/7afbafd03fdcbd464305fe6f0592141117d3527c))

## 0.3.0 (2025-08-14)

Full Changelog: [v0.2.10...v0.3.0](https://github.com/scaleapi/agentex-python/compare/v0.2.10...v0.3.0)

### Features

* **api:** api update ([ad779b4](https://github.com/scaleapi/agentex-python/commit/ad779b4ce6a9f21b4f69c88770269b404ac25818))
* **api:** manual updates ([9dc2f75](https://github.com/scaleapi/agentex-python/commit/9dc2f7511750884ec6754d91e6d27592f85b72e5))

## 0.2.10 (2025-08-13)

Full Changelog: [v0.2.9...v0.2.10](https://github.com/scaleapi/agentex-python/compare/v0.2.9...v0.2.10)

## 0.2.9 (2025-08-12)

Full Changelog: [v0.2.8...v0.2.9](https://github.com/scaleapi/agentex-python/compare/v0.2.8...v0.2.9)

### Chores

* **internal:** update test skipping reason ([4affc92](https://github.com/scaleapi/agentex-python/commit/4affc925c69ed626d429732b470d4d1535b1be8d))

## 0.2.8 (2025-08-09)

Full Changelog: [v0.2.7...v0.2.8](https://github.com/scaleapi/agentex-python/compare/v0.2.7...v0.2.8)

### Chores

* **internal:** update comment in script ([401f1d7](https://github.com/scaleapi/agentex-python/commit/401f1d79034ecb0b556a26debde79681bc21e8ae))
* update @stainless-api/prism-cli to v5.15.0 ([4d332d0](https://github.com/scaleapi/agentex-python/commit/4d332d0f77a5a11ca6781a5fc7690ae82653cadb))

## 0.2.7 (2025-08-08)

Full Changelog: [v0.2.6...v0.2.7](https://github.com/scaleapi/agentex-python/compare/v0.2.6...v0.2.7)

### Features

* **api:** api update ([e3d08ba](https://github.com/scaleapi/agentex-python/commit/e3d08baad59346db48e04a394a929d6347dafa07))
* debug features ([40d8db2](https://github.com/scaleapi/agentex-python/commit/40d8db22dcc8f00a6c78e9bc3e1d036ebd1423b6))


### Chores

* **internal:** fix ruff target version ([1b880e1](https://github.com/scaleapi/agentex-python/commit/1b880e1dd81d47bb9df12507f13351611ff6367f))

## 0.2.6 (2025-08-01)

Full Changelog: [v0.2.5...v0.2.6](https://github.com/scaleapi/agentex-python/compare/v0.2.5...v0.2.6)

### Features

* **api:** add query params to tasks.list ([d4902d5](https://github.com/scaleapi/agentex-python/commit/d4902d52caf82e2f57d1bbf19527cdc1448ed397))
* **client:** support file upload requests ([e004b30](https://github.com/scaleapi/agentex-python/commit/e004b304c22286151330c2200bcb85046a7ac111))

## 0.2.5 (2025-07-30)

Full Changelog: [v0.2.4...v0.2.5](https://github.com/scaleapi/agentex-python/compare/v0.2.4...v0.2.5)

### Features

* **api:** api update ([f90002c](https://github.com/scaleapi/agentex-python/commit/f90002c247a94cddc17307fb4eded12359cc9ad8))
* **api:** api update ([aee4ad1](https://github.com/scaleapi/agentex-python/commit/aee4ad10e588386e9af1b4828d16ddba1805dca0))
* **api:** manual updates ([55efcdd](https://github.com/scaleapi/agentex-python/commit/55efcdd55f2a20d1172da95cd551751d8be0d0df))

## 0.2.4 (2025-07-29)

Full Changelog: [v0.2.3...v0.2.4](https://github.com/scaleapi/agentex-python/compare/v0.2.3...v0.2.4)

## 0.2.3 (2025-07-29)

Full Changelog: [v0.2.2...v0.2.3](https://github.com/scaleapi/agentex-python/compare/v0.2.2...v0.2.3)

## 0.2.2 (2025-07-28)

Full Changelog: [v0.2.1...v0.2.2](https://github.com/scaleapi/agentex-python/compare/v0.2.1...v0.2.2)

### Features

* **api:** api update ([eb79533](https://github.com/scaleapi/agentex-python/commit/eb79533dd041b7fccccc6a75abedd0c87e9c55e5))

## 0.2.1 (2025-07-27)

Full Changelog: [v0.2.0...v0.2.1](https://github.com/scaleapi/agentex-python/compare/v0.2.0...v0.2.1)

## 0.2.0 (2025-07-25)

Full Changelog: [v0.1.1...v0.2.0](https://github.com/scaleapi/agentex-python/compare/v0.1.1...v0.2.0)

### Features

* **api:** update typescript sdk with big changes ([2c75d64](https://github.com/scaleapi/agentex-python/commit/2c75d642348df727505778c347efa568930ea4f0))


### Chores

* **project:** add settings file for vscode ([0f926cc](https://github.com/scaleapi/agentex-python/commit/0f926cce7df375de33627f8212caacf64f89b1ed))

## 0.1.1 (2025-07-24)

Full Changelog: [v0.1.0...v0.1.1](https://github.com/scaleapi/agentex-python/compare/v0.1.0...v0.1.1)

### Features

* **api:** manual updates ([714e97e](https://github.com/scaleapi/agentex-python/commit/714e97ed1813a4a91b421fb77fadaf2afac2450d))
* **api:** manual updates ([8dccfbd](https://github.com/scaleapi/agentex-python/commit/8dccfbdd9b8b887bfb99c79a9a28163215560ae4))
* **api:** manual updates ([03af884](https://github.com/scaleapi/agentex-python/commit/03af884e31a3df4d42a863c06c5ab4dfc2374374))

## 0.1.0 (2025-07-23)

Full Changelog: [v0.1.0-alpha.6...v0.1.0](https://github.com/scaleapi/agentex-python/compare/v0.1.0-alpha.6...v0.1.0)

### Features

* **api:** manual updates ([84010e4](https://github.com/scaleapi/agentex-python/commit/84010e4adecf7c779abd9a828000a3b50d9d3ac3))

## 0.1.0-alpha.6 (2025-07-23)

Full Changelog: [v0.1.0-alpha.5...v0.1.0-alpha.6](https://github.com/scaleapi/agentex-python/compare/v0.1.0-alpha.5...v0.1.0-alpha.6)

### Features

* **api:** api update ([af18034](https://github.com/scaleapi/agentex-python/commit/af18034e4173794ebf42eff688f26d64caca4e64))
* **api:** api update ([be9b603](https://github.com/scaleapi/agentex-python/commit/be9b60326817566d5c5edcbd7b7babb6db07e539))
* **api:** manual updates ([bbe3be3](https://github.com/scaleapi/agentex-python/commit/bbe3be30aa9fb8d7a677f0e9f0be4dd565563d6e))

## 0.1.0-alpha.5 (2025-07-23)

Full Changelog: [v0.1.0-alpha.4...v0.1.0-alpha.5](https://github.com/scaleapi/agentex-python/compare/v0.1.0-alpha.4...v0.1.0-alpha.5)

### Features

* **api:** deprecate name subresource ([14881c0](https://github.com/scaleapi/agentex-python/commit/14881c0ff2922e0a622975a0f5b314de99d7aabb))
* **api:** manual updates ([d999a43](https://github.com/scaleapi/agentex-python/commit/d999a438c409f04b7e36b5df2d9b080d1d1b0e4a))
* **api:** manual updates ([a885d8d](https://github.com/scaleapi/agentex-python/commit/a885d8dbabfe2cc2a556ef02e75e5502fd799c46))


### Bug Fixes

* **api:** build errors ([7bde6b7](https://github.com/scaleapi/agentex-python/commit/7bde6b727d6d16ebd6805ef843596fc3224445a6))
* **parsing:** parse extra field types ([d40e6e0](https://github.com/scaleapi/agentex-python/commit/d40e6e0d6911be0bc9bfc419e02bd7c1d5ad5be4))

## 0.1.0-alpha.4 (2025-07-22)

Full Changelog: [v0.1.0-alpha.3...v0.1.0-alpha.4](https://github.com/scaleapi/agentex-python/compare/v0.1.0-alpha.3...v0.1.0-alpha.4)

## 0.1.0-alpha.3 (2025-07-22)

Full Changelog: [v0.1.0-alpha.2...v0.1.0-alpha.3](https://github.com/scaleapi/agentex-python/compare/v0.1.0-alpha.2...v0.1.0-alpha.3)

### Features

* **api:** api update ([afedf45](https://github.com/scaleapi/agentex-python/commit/afedf4541ba6219cd04ef7af39a1d451abde75a4))

## 0.1.0-alpha.2 (2025-07-22)

Full Changelog: [v0.1.0-alpha.1...v0.1.0-alpha.2](https://github.com/scaleapi/agentex-python/compare/v0.1.0-alpha.1...v0.1.0-alpha.2)

## 0.1.0-alpha.1 (2025-07-22)

Full Changelog: [v0.0.1-alpha.1...v0.1.0-alpha.1](https://github.com/scaleapi/agentex-python/compare/v0.0.1-alpha.1...v0.1.0-alpha.1)

### Features

* **api:** manual updates ([06f5fe1](https://github.com/scaleapi/agentex-python/commit/06f5fe115ace5ec4ca8149cd0afa6207b193a04c))

## 0.0.1-alpha.1 (2025-07-22)

Full Changelog: [v0.0.1-alpha.0...v0.0.1-alpha.1](https://github.com/scaleapi/agentex-python/compare/v0.0.1-alpha.0...v0.0.1-alpha.1)

### Chores

* sync repo ([bc305f4](https://github.com/scaleapi/agentex-python/commit/bc305f43efedb5b7d7b28eaa059bce1d280c9dbb))
* update SDK settings ([e5a06b4](https://github.com/scaleapi/agentex-python/commit/e5a06b4e3d8f8ad15d55b92393d7ddd833415f86))
