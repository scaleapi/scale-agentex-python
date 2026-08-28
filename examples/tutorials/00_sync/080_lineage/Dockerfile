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
COPY 00_sync/080_lineage/pyproject.toml /app/080_lineage/pyproject.toml
COPY 00_sync/080_lineage/README.md /app/080_lineage/README.md

WORKDIR /app/080_lineage

# Copy the project code
COPY 00_sync/080_lineage/project /app/080_lineage/project

# Copy the test files
COPY 00_sync/080_lineage/tests /app/080_lineage/tests

# Copy shared test utilities
COPY test_utils /app/test_utils

# Install the required Python packages with dev dependencies
RUN uv pip install --system .[dev]

# Set environment variables
ENV PYTHONPATH=/app

# Set test environment variables
ENV AGENT_NAME=s080-lineage

# The agent build version stamped onto every span as __agent_version__.
# Real deployments pass the image tag or git SHA at build time.
ARG AGENT_VERSION=0.1.0
ENV AGENT_VERSION=${AGENT_VERSION}

# Run the agent using uvicorn
CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]
