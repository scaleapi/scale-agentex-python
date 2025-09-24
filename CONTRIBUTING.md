## Setting up the environment

We use [UV](https://docs.astral.sh/uv/) for fast, modern Python package management. UV automatically handles Python installation and virtual environment management.

### Quick Setup

```sh
# Setup environment and dependencies
$ uv run task bootstrap

# Install pre-commit hooks
$ uv run task setup-pre-commit
```

### Manual Setup

If you prefer to install UV manually:

```sh
# Install UV - https://docs.astral.sh/uv/getting-started/installation/
$ curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
$ uv sync --all-extras --group dev
```

You can then run commands using `uv run` or by activating the virtual environment:

```sh
# Activate the virtual environment
$ source .venv/bin/activate

# Now you can omit the `uv run` prefix
$ python script.py
```

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
$ pip install git+ssh://git@github.com/scaleapi/agentex-python.git
```

Alternatively, you can build from source and install the wheel file:

Building this package will create two files in the `dist/` directory, a `.tar.gz` containing the source files and a `.whl` that can be used to install the package efficiently.

To create a distributable version of the library, all you have to do is run this command:

```sh
$ uv build
# or
$ uv run task ci-build
```

Then to install:

```sh
$ pip install ./path-to-wheel-file.whl
```

## Development Workflow

We use [Taskipy](https://github.com/taskipy/taskipy) to manage development tasks. All commands are defined in `pyproject.toml` and can be run with `uv run task <command>`.

### Running tests

```sh
# Run tests with automatic mock server management
$ uv run task test

# Or run tests directly (no mock server setup)
$ uv run pytest
```

The test command automatically handles [Prism mock server](https://github.com/stoplightio/prism) setup and teardown using the OpenAPI spec.

### Linting and formatting

```sh
# Format code and documentation
$ uv run task format

# Run all linting checks
$ uv run task lint

# Run type checking only
$ uv run task typecheck
```

### Available Tasks

```sh
# See all available tasks
$ uv run task --list
```

Key tasks:
- `bootstrap` - Set up development environment
- `format` - Format code with Ruff and documentation
- `lint` - Run all checks (Ruff + type checking + import validation)
- `test` - Run tests with mock server orchestration
- `mock` - Start standalone mock API server
- `setup-pre-commit` - Install pre-commit hooks

## Publishing and releases

Changes made to this repository via the automated release PR pipeline should publish to PyPI automatically. If
the changes aren't made through the automated pipeline, you may want to make releases manually.

### Publish with a GitHub workflow

You can release to package managers by using [the `Publish PyPI` GitHub action](https://www.github.com/scaleapi/agentex-python/actions/workflows/publish-pypi.yml). This requires a setup organization or repository secret to be set up.

### Publish manually

If you need to manually release a package, you can use UV directly:

```sh
$ uv build
$ uv publish --token $PYPI_TOKEN
```

## 🤖 **Vibe Coding Setup**

This repository is setup with some pre-canned prompts for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) as well as [Cursor](https://cursor.com/).

### Cursor

Access to Cursor can be acquired by asking for it in #it-help.  Then just loading this repo in the Cursor IDE should enable the prompts.

### Claude Code

### 1. Install Claude Code
```bash
npm install -g @anthropic-ai/claude-code
```

### 2. Request a LiteLLM API Key
Visit the [LiteLLM User Guide](https://scale.atlassian.net/wiki/spaces/EPD/pages/1490354189/LiteLLM+User+Guide#Requesting-LiteLLM-Key-for-Generic-Usage) to request your API key.

### 3. Set Environment Variables
```bash
export ANTHROPIC_AUTH_TOKEN=${LITELLM_PROXY_API_KEY}
export ANTHROPIC_BASE_URL="https://litellm.ml-serving-internal.scale.com"
```

### 4. Start Claude Code
```bash
claude
```
This should be run from inside the main repo directory. If you run the command from a terminal inside VSCode, then Claude will use the VSCode editor to show diffs etc. 