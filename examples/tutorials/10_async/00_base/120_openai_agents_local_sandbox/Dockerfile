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
COPY 10_async/00_base/120_openai_agents_local_sandbox/pyproject.toml /app/120_openai_agents_local_sandbox/pyproject.toml
COPY 10_async/00_base/120_openai_agents_local_sandbox/README.md /app/120_openai_agents_local_sandbox/README.md

WORKDIR /app/120_openai_agents_local_sandbox

# Copy the project code
COPY 10_async/00_base/120_openai_agents_local_sandbox/project /app/120_openai_agents_local_sandbox/project

# Copy the test files
COPY 10_async/00_base/120_openai_agents_local_sandbox/tests /app/120_openai_agents_local_sandbox/tests

# Copy shared test utilities
COPY test_utils /app/test_utils

# Install the required Python packages with dev dependencies
RUN uv pip install --system .[dev] pytest-asyncio httpx

# Set environment variables
ENV PYTHONPATH=/app

# Set test environment variables
ENV AGENT_NAME=ab120-openai-agents-local-sandbox

# Run the agent using uvicorn
CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]
