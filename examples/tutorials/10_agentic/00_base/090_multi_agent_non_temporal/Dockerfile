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

# Copy just the pyproject.toml file to optimize caching
COPY pyproject.toml /app/pyproject.toml
WORKDIR /app/
# Install the required Python packages
RUN uv pip install --system -e .

# Copy the project code
COPY project /app/project

WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app

ARG AGENT_FILE
ARG PORT

# Run the agent using uvicorn
CMD uvicorn project.${AGENT_FILE%.*}:acp --host 0.0.0.0 --port ${PORT:-8000}
