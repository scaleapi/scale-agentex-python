# syntax=docker/dockerfile:1.3
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.6.4 /uv /uvx /bin/

# Install system dependencies
RUN apt-get update && apt-get install -y \
    htop \
    vim \
    curl \
    tar \
    python3-dev \
    postgresql-client \
    build-essential \
    libpq-dev \
    gcc \
    cmake \
    netcat-openbsd \
    nodejs \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install the codex CLI: the agent spawns `codex exec --json`, so the binary
# must be present on PATH in the image.
RUN npm install -g @openai/codex

RUN uv pip install --system --upgrade pip setuptools wheel

ENV UV_HTTP_TIMEOUT=1000

COPY 10_async/00_base/140_codex/pyproject.toml /app/140_codex/pyproject.toml
COPY 10_async/00_base/140_codex/README.md /app/140_codex/README.md

WORKDIR /app/140_codex

COPY 10_async/00_base/140_codex/project /app/140_codex/project
COPY 10_async/00_base/140_codex/tests /app/140_codex/tests
COPY test_utils /app/test_utils

RUN uv pip install --system .[dev]

ENV PYTHONPATH=/app
ENV AGENT_NAME=ab140-codex

CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]
