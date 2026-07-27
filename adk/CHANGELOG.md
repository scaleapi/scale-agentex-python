# Changelog

## 0.20.0 (2026-07-16)

Full Changelog: [agentex-sdk-v0.19.0...agentex-sdk-v0.20.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.19.0...agentex-sdk-v0.20.0)

### Chores

* **agentex-sdk:** Synchronize agentex versions

## 0.19.0 (2026-07-14)

Full Changelog: [agentex-sdk-v0.18.0...agentex-sdk-v0.19.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.18.0...agentex-sdk-v0.19.0)

### Chores

* **agentex-sdk:** Synchronize agentex versions

## 0.18.0 (2026-07-10)

Full Changelog: [agentex-sdk-v0.17.0...agentex-sdk-v0.18.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.17.0...agentex-sdk-v0.18.0)

### Bug Fixes

* cap openai &lt;2.45 for openai-agents 0.14.x compatibility ([#459](https://github.com/scaleapi/scale-agentex-python/issues/459)) ([14c124d](https://github.com/scaleapi/scale-agentex-python/commit/14c124d363ed964ed8c08e10a95ca3939095ea92))


### Chores

* **internal:** version bump ([7aeb893](https://github.com/scaleapi/scale-agentex-python/commit/7aeb8937bb794586f7d5931bdc5964d007762b4c))
* **internal:** version bump ([fcddeea](https://github.com/scaleapi/scale-agentex-python/commit/fcddeea8ef4bdff0a5f7735156c3003166464eac))

## 0.17.0 (2026-07-01)

Full Changelog: [agentex-sdk-v0.16.2...agentex-sdk-v0.17.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.16.2...agentex-sdk-v0.17.0)

### Chores

* **agentex-sdk:** Synchronize agentex versions

## 0.16.2 (2026-06-29)

Full Changelog: [agentex-sdk-v0.15.0...agentex-sdk-v0.16.2](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.15.0...agentex-sdk-v0.16.2)

### Bug Fixes

* **adk:** release streaming buffer repair in sdk ([#449](https://github.com/scaleapi/scale-agentex-python/issues/449)) ([20795cb](https://github.com/scaleapi/scale-agentex-python/commit/20795cb158244767207b6d3758929014bc015bb6))

## 0.15.0 (2026-06-24)

Full Changelog: [agentex-sdk-v0.14.0...agentex-sdk-v0.15.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.14.0...agentex-sdk-v0.15.0)

### ⚠ BREAKING CHANGES

* **harness:** consolidate the LangGraph harness + remove tracing handler ([#430](https://github.com/scaleapi/scale-agentex-python/issues/430))

### Bug Fixes

* **harness:** harden Claude Code + OpenAI taps and span tracing ([#446](https://github.com/scaleapi/scale-agentex-python/issues/446)) ([5b4359d](https://github.com/scaleapi/scale-agentex-python/commit/5b4359dcf28f390f780215ed954fa52e8cb4dd7c))


### Refactors

* **harness:** consolidate the LangGraph harness + remove tracing handler ([#430](https://github.com/scaleapi/scale-agentex-python/issues/430)) ([a3fb5ad](https://github.com/scaleapi/scale-agentex-python/commit/a3fb5ad51f6392a48cbb8324f15c9619f10244b6))

## 0.14.0 (2026-06-23)

Full Changelog: [agentex-sdk-v0.13.2...agentex-sdk-v0.14.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.13.2...agentex-sdk-v0.14.0)

### Features

* **harness:** public adk facade + docs for the unified harness surface (PR 9) ([#423](https://github.com/scaleapi/scale-agentex-python/issues/423)) ([fa60632](https://github.com/scaleapi/scale-agentex-python/commit/fa60632f9be84315a3fdc627745ae5b605994bd8))

## 0.13.2 (2026-06-22)

Full Changelog: [agentex-sdk-v0.13.1...agentex-sdk-v0.13.2](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.13.1...agentex-sdk-v0.13.2)

## 0.13.1 (2026-06-17)

Full Changelog: [agentex-sdk-v0.13.0...agentex-sdk-v0.13.1](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.13.0...agentex-sdk-v0.13.1)

### Bug Fixes

* **packaging:** guard agentex-client surface, bump floor, smoke-test wheel install ([#406](https://github.com/scaleapi/scale-agentex-python/issues/406)) ([a5abbb9](https://github.com/scaleapi/scale-agentex-python/commit/a5abbb9669c6ab71c52e60db72676c95c20d840d))


### Documentation

* drop stale keep_files / dashboard-config comments ([#401](https://github.com/scaleapi/scale-agentex-python/issues/401)) ([23858df](https://github.com/scaleapi/scale-agentex-python/commit/23858df775d0a617c6418eed28f1b68c9bf9ed5c))

## 0.13.0 (2026-06-10)

Full Changelog: [agentex-sdk-v0.12.0...agentex-sdk-v0.13.0](https://github.com/scaleapi/scale-agentex-python/compare/agentex-sdk-v0.12.0...agentex-sdk-v0.13.0)

### ⚠ BREAKING CHANGES

* **packaging:** release tag scheme changes from v* to <component>-v*.

### Features

* **packaging:** introduce slim agentex-client + heavy agentex-sdk split ([bbfb22e](https://github.com/scaleapi/scale-agentex-python/commit/bbfb22eb113dd1f3d5ddf82b4d377895f5ae5466))
