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

COPY 10_async/10_temporal/120_openai_agents/pyproject.toml /app/120_openai_agents/pyproject.toml
COPY 10_async/10_temporal/120_openai_agents/README.md /app/120_openai_agents/README.md

WORKDIR /app/120_openai_agents

COPY 10_async/10_temporal/120_openai_agents/project /app/120_openai_agents/project
COPY 10_async/10_temporal/120_openai_agents/tests /app/120_openai_agents/tests
COPY test_utils /app/test_utils

RUN uv pip install --system .[dev]

ENV PYTHONPATH=/app

ENV AGENT_NAME=at120-openai-agents

CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]

# When we deploy the worker, we will replace the CMD with the following
# CMD ["python", "-m", "run_worker"]
