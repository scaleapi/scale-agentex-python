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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN uv pip install --system --upgrade pip setuptools wheel

ENV UV_HTTP_TIMEOUT=1000

# Copy pyproject.toml and README.md to install dependencies
COPY 090_multi_agent_non_temporal/pyproject.toml /app/090_multi_agent_non_temporal/pyproject.toml
COPY 090_multi_agent_non_temporal/README.md /app/090_multi_agent_non_temporal/README.md

WORKDIR /app/090_multi_agent_non_temporal

# Copy the project code
COPY 090_multi_agent_non_temporal/project /app/090_multi_agent_non_temporal/project

# Copy the test files
COPY 090_multi_agent_non_temporal/tests /app/090_multi_agent_non_temporal/tests

# Copy shared test utilities
COPY test_utils /app/test_utils

# Install the required Python packages with dev dependencies (includes pytest)
RUN uv pip install --system .[dev] pytest-asyncio httpx

# Set environment variables
ENV PYTHONPATH=/app

ARG AGENT_FILE
ARG PORT

# Note: AGENT_NAME should be set at runtime based on which agent is running
# (ab090-creator-agent, ab090-critic-agent, ab090-formatter-agent, or ab090-orchestrator-agent)

# Run the agent using uvicorn
CMD uvicorn project.${AGENT_FILE%.*}:acp --host 0.0.0.0 --port ${PORT:-8000}
