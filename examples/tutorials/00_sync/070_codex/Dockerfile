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

# Copy pyproject.toml and README.md to install dependencies
COPY 00_sync/070_codex/pyproject.toml /app/070_codex/pyproject.toml
COPY 00_sync/070_codex/README.md /app/070_codex/README.md

WORKDIR /app/070_codex

# Copy the project code
COPY 00_sync/070_codex/project /app/070_codex/project

# Copy the test files
COPY 00_sync/070_codex/tests /app/070_codex/tests

# Copy shared test utilities
COPY test_utils /app/test_utils

# Install the required Python packages with dev dependencies
RUN uv pip install --system .[dev]

# Set environment variables
ENV PYTHONPATH=/app

# Set test environment variables
ENV AGENT_NAME=s070-codex

# Run the agent using uvicorn
CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]
