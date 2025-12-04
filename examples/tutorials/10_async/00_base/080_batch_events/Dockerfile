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
COPY 10_async/00_base/080_batch_events/pyproject.toml /app/080_batch_events/pyproject.toml
COPY 10_async/00_base/080_batch_events/README.md /app/080_batch_events/README.md

WORKDIR /app/080_batch_events

# Copy the project code
COPY 10_async/00_base/080_batch_events/project /app/080_batch_events/project

# Copy the test files
COPY 10_async/00_base/080_batch_events/tests /app/080_batch_events/tests

# Copy shared test utilities
COPY test_utils /app/test_utils

# Install the required Python packages with dev dependencies (includes pytest)
RUN uv pip install --system .[dev] pytest-asyncio httpx

WORKDIR /app/080_batch_events
# Set environment variables
ENV PYTHONPATH=/app

# Set test environment variables
ENV AGENT_NAME=ab080-batch-events

# Run the agent using uvicorn
CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]
