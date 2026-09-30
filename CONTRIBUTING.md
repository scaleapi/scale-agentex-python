## Setting up the environment

### With `uv`

We use [uv](https://docs.astral.sh/uv/) to manage dependencies because it will automatically provision a Python environment with the expected Python version. To set it up, run:

```sh
$ ./scripts/bootstrap
```

Or [install uv manually](https://docs.astral.sh/uv/getting-started/installation/) and run:

```sh
$ uv sync --all-extras
```

You can then run scripts using `uv run python script.py` or by manually activating the virtual environment:

```sh
# manually activate - https://docs.python.org/3/library/venv.html#how-venvs-work
$ source .venv/bin/activate

# now you can omit the `uv run` prefix
$ python script.py
```

### Without `uv`

Alternatively if you don't want to install `uv`, you can stick with the standard `pip` setup by ensuring you have the Python version specified in `.python-version`, create a virtual environment however you desire and then install dependencies using this command:

```sh
$ pip install -r requirements-dev.lock
```

## Contribution workflow

This repository is generated and released by [Stainless](https://www.stainless.com/). To keep the
release pipeline working, contributions need to follow the branch model and commit conventions below.

### Branch model

- Open PRs against `main`, the only integration branch. There is no `next` branch any more, and no
  label is needed.
- Typical flow:
  1. Pull the latest `main` locally and branch off it.
  2. Make and push your changes, then open a PR targeting `main`.
  3. Get the PR reviewed and merged into `main`.
  4. release-please keeps a release PR open on `main` that bumps the version and changelog. Merging
     that PR cuts the release and publishes it to PyPI.
- Most of the SDK is generated from the API spec. Changes to the API surface belong in the spec in
  [scaleapi/scale-agentex](https://github.com/scaleapi/scale-agentex) (`agentex/openapi.yaml`), not
  in generated files, where hand edits are replayed onto every regeneration and can conflict with
  it. Hand-written code lives in `src/agentex/lib/` and `examples/`, which the generator never
  modifies.

#### For maintainers

- Promote PRs (`chore: promote staging … to production`) open as drafts. Approve them, but never
  mark them ready for review or merge them; once their checks are green, re-run the promote
  workflow, which fast-forwards `main`.
- Merge a human PR into `main` only while staging `main` is an ancestor of production `main` and no
  codegen run is in flight, then run the back-sync workflow (`stlc-sync.yml` in
  scaleapi/scale-agentex).
- Promote, then release, in one sitting.
- See the runbook at the top of `.github/workflows/stlc-promote.yml` in scaleapi/scale-agentex for
  details.

### Conventional commits

Commit messages and PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/),
because the changelog and release notes are derived from them. The `Validate PR title (Conventional Commits)`
CI check enforces this on every PR. Common prefixes:

- `feat(api): ...` — new functionality
- `fix(types): ...` — bug fixes
- `docs(readme): ...` — documentation-only changes (required for manual README/docs overrides to be
  picked up by the generator)
- `chore(internal): ...` — internal changes that don't affect users

## Modifying/Adding code

Most of the SDK is generated code. Modifications to code will be persisted between generations, but may
result in merge conflicts between manual patches and changes from the generator. The generator will never
modify the contents of the `src/agentex/lib/` and `examples/` directories.

## Adding and running examples

All files in the `examples/` directory are not modified by the generator and can be freely edited or added to.

```py
# add an example to examples/<your-example>.py

#!/usr/bin/env -S uv run python
…
```

```sh
$ chmod +x examples/<your-example>.py
# run the example against your api
$ ./examples/<your-example>.py
```

## Using the repository from source

If you’d like to use the repository from source, you can either install from git or link to a cloned repository:

To install via git:

```sh
$ pip install git+ssh://git@github.com/scaleapi/scale-agentex-python.git
```

Alternatively, you can build from source and install the wheel file:

Building this package will create two files in the `dist/` directory, a `.tar.gz` containing the source files and a `.whl` that can be used to install the package efficiently.

To create a distributable version of the library, all you have to do is run this command:

```sh
$ uv build
# or
$ python -m build
```

Then to install:

```sh
$ pip install ./path-to-wheel-file.whl
```

## Running tests

```sh
$ ./scripts/test
```

## Linting and formatting

This repository uses [ruff](https://github.com/astral-sh/ruff) and
[black](https://github.com/psf/black) to format the code in the repository.

To lint:

```sh
$ ./scripts/lint
```

To format and fix all ruff issues automatically:

```sh
$ ./scripts/format
```

## Publishing and releases

Changes made to this repository via the automated release PR pipeline should publish to PyPI automatically. If
the changes aren't made through the automated pipeline, you may want to make releases manually.

### Publish with a GitHub workflow

You can release to package managers by using [the `Publish PyPI` GitHub action](https://www.github.com/scaleapi/scale-agentex-python/actions/workflows/publish-pypi.yml). This requires a setup organization or repository secret to be set up.

### Publish manually

If you need to manually release a package, you can run the `bin/publish-pypi` script with a `PYPI_TOKEN` set on
the environment.

## 🤖 **Vibe Coding Setup**

This repository is setup with some pre-canned prompts for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) as well as [Cursor](https://cursor.com/).

