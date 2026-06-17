# Datadog APM instrumentation for Agentex agents

## Use exactly one ddtrace auto-instrumentation entry point per process

The SGP platform enables Datadog **single-step instrumentation (SSI)** on every
agentex pod (`admission.datadoghq.com/enabled: "true"` in the sgp helm charts).
SSI injects ddtrace and auto-instruments FastAPI for you. Agent code and
deployment config must therefore **not add a second entry point**:

- Do **not** call `ddtrace.patch_all()` or `import ddtrace.auto` in your agent.
- Do **not** wrap the launch command with `ddtrace-run` (the ACP server is started
  as a plain `uvicorn project.acp:acp`).

Two entry points layer two ddtrace copies whose de-dupe guards don't cross-recognize
each other, so ddtrace wraps the route handler twice.

**Local / non-SSI environments:** without the platform admission controller there is
no SSI, so FastAPI is not auto-instrumented. If you want APM locally, run the server
under `ddtrace-run` — but only in that environment, and never alongside SSI.

**Pin your tracing libraries.** Floor-only pins (`ddtrace>=...`, `fastapi>=...`,
`starlette>=...`) let each image rebuild pull whatever is latest, which can drift away
from the platform-injected ddtrace version and is a latent source of cross-copy
instrumentation mismatches. Pin ddtrace (and fastapi/starlette) to known-good versions.

## Symptom of a double-instrumentation regression

ddtrace's `resource_name` / `http.route` doubles the router prefix —
`POST /api/api`, `GET /healthz/healthz` — coexisting with the correct single-prefix
names. The **served URL is unaffected** (`http.url`, `http.path_group`,
`http.inferred_route` stay single), so traffic works but monitors and dashboards
filtered on `resource_name:post_/api` silently miss the doubled fraction.

The ACP server logs a `WARNING` at startup when it detects more than one ddtrace
wrap on its route handler (`_warn_if_double_instrumented` in `base_acp_server.py`).
The check is best-effort — it reads ddtrace/wrapt internals and silently no-ops if
those shift, so treat it as a heads-up, not a hard gate. If you see it, remove the
in-app `patch_all()` / `ddtrace-run` and rely on SSI.

## Emitting custom spans

You don't need `patch_all()` to add your own spans. With SSI active,
`ddtrace.tracer` is the injected tracer — `with tracer.trace(...)` and
`span.set_tag(...)` work as-is. For Scale Groundplane spans use `adk.tracing`.

## Restoring monitor coverage after a doubling incident

`http.path_group` and `http.inferred_route` are derived from the request URL, not
from the doubled tracer resource, so they stay single. Monitors and dashboards
should filter on `@http.path_group:/api` (or `@http.inferred_route:/api`) rather
than `resource_name:post_/api` — this is robust whether or not the doubling recurs.
