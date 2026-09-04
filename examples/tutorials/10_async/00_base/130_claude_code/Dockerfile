# syntax=docker/dockerfile:1.3
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.6.4 /uv /uvx /bin/

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

RUN uv pip install --system --upgrade pip setuptools wheel

RUN npm install -g @anthropic-ai/claude-code || true

ENV UV_HTTP_TIMEOUT=1000

COPY 10_async/00_base/130_claude_code/pyproject.toml /app/130_claude_code/pyproject.toml
COPY 10_async/00_base/130_claude_code/README.md /app/130_claude_code/README.md

WORKDIR /app/130_claude_code

COPY 10_async/00_base/130_claude_code/project /app/130_claude_code/project
COPY 10_async/00_base/130_claude_code/tests /app/130_claude_code/tests
COPY test_utils /app/test_utils

RUN uv pip install --system .[dev]

ENV PYTHONPATH=/app

ENV AGENT_NAME=ab130-claude-code

CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]
