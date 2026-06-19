"""Deployment & agent configuration shapes for Agentex.

The modules under `agentex.config.*` are the typed manifest/deployment
configuration models (agent, build, deployment, environment, local-dev) plus
their leaf model deps (credentials, temporal). They depend only on pydantic,
so they are safe to import from a slim REST-only install without the ADK
runtime.

For back-compat, the same classes are re-exported from their historical
locations under `agentex.lib.sdk.config.*` and
`agentex.lib.types.{agent_configs,credentials}`. The yaml-loading helpers
(`load_environments_config*`) stay in `agentex.lib.sdk.config.environment_config`
so the promoted models remain slim-safe.
"""
