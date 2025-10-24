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
COPY 080_batch_events/pyproject.toml /app/080_batch_events/pyproject.toml
COPY 080_batch_events/README.md /app/080_batch_events/README.md

WORKDIR /app/080_batch_events

# Copy the project code
COPY 080_batch_events/project /app/080_batch_events/project

# Copy test files
COPY 080_batch_events/test_*.py /app/080_batch_events/

# Install the required Python packages from pyproject.toml
RUN uv pip install --system .

# Install pytest for running tests
RUN uv pip install --system pytest pytest-asyncio

WORKDIR /app/080_batch_events
# Set environment variables
ENV PYTHONPATH=/app

# Run the agent using uvicorn
CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]
