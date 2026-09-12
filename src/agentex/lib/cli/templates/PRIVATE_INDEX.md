# The private package index in scaffold Dockerfiles

Every scaffold Dockerfile mounts a build secret named `codeartifact-pip-conf`. It lets an agent
install Scale-internal packages — `sgp-obs`, for instance — that are not on public PyPI, without the
build holding any registry credential of its own. The control-plane broker mints a short-lived
CodeArtifact token per build and injects it as that secret.

- Design: [Private Package Access for Customer Agents (PRD)](https://app.notion.com/p/Private-Package-Access-for-Customer-Agents-PRD-3ad904d6e6cb802cb091df1c25e230bc)
- Tracking: [SGPINF-1568](https://linear.app/scale-epd/issue/SGPINF-1568/provide-scale-internal-packages-to-agentex-agents-in-customer)

## It is inert by default

The mount is `required=false` and guarded by `[ -s ... ]`, so with no secret injected the build is
byte-identical to one without any of this. That covers every local build, every CI build, and every
agent that never opts in. An empty secret file is skipped too.

## Opting in

Add the index to the agent's `pyproject.toml`:

```toml
[[tool.uv.index]]
name = "scale-pypi"
url = "<the scale-customer-pypi URL>"
default = true
```

The name must be exactly `scale-pypi`. uv applies `UV_INDEX_SCALE_PYPI_USERNAME` /
`UV_INDEX_SCALE_PYPI_PASSWORD` to the index of that name, so renaming it makes the credentials
silently stop applying. Setting `UV_INDEX_URL` instead does not authenticate a *named* index at
all, and the resolve fails with a 401.

## Three things that are easy to get wrong

**The token arrives percent-encoded.** The buildspec URL-encodes it to embed it in the pip config's
URL userinfo, so a token containing `+`, `/` or `=` arrives as `%2B`, `%2F`, `%3D`. The `uv sync`
templates decode it before exporting it as a password. Passing it through still-encoded sends a
different string and the resolve 401s.

**The credential must not follow project-controlled configuration.** uv binds credentials by index
*name*, and the name-to-URL mapping would otherwise come from the agent's own `pyproject.toml` — so a
project that pointed `scale-pypi` at another host would receive the token. Verified against a local
server: the rogue host receives `Authorization: Basic aws:<token>` and the real index is never
contacted. The templates therefore export `UV_INDEX` to re-bind the name to the URL the *broker*
supplied, which overrides whatever the project declared. With that in place the rogue host is never
contacted. The pinned URL carries no userinfo; the token still travels only in
`UV_INDEX_SCALE_PYPI_PASSWORD`.

The case this defends is not a malicious agent author — they also write the Dockerfile and could read
the mounted secret directly. It is a *contributed* change to a project file, where a one-line URL edit
is far less conspicuous in review than an exfiltration command in a Dockerfile.

**The two template variants work differently, deliberately.**

| Template | Install step | How the credential is supplied |
| --- | --- | --- |
| `Dockerfile-uv.j2` | `uv sync` against the agent's `pyproject.toml` | Named index `scale-pypi`, pinned via `UV_INDEX`, token decoded into `UV_INDEX_SCALE_PYPI_PASSWORD` |
| `Dockerfile.j2` | `uv pip install -r requirements.txt` | No pyproject is present, so there is no named index to bind to. The credentialed URL is used directly via `UV_DEFAULT_INDEX` |

The `requirements.txt` variant does **not** decode the token, and that is the point: it stays inside
the URL, already encoded for exactly that use. Decoding it there would corrupt it. It is also not
exposed to the redirection problem above, because the URL comes wholly from the injected secret.
