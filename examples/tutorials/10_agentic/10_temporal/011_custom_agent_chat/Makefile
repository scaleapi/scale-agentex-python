install-dev:
	uv sync --group dev

dev: install-dev
	uv run --env-file=.env agentex agents run --manifest manifest.yaml

typecheck: install-dev
	uv run mypy project --strict
