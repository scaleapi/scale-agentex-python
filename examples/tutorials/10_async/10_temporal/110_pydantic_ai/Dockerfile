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
# Fewer parallel PyPI downloads, so the slow emulated arm64 build drops fewer connections.
ENV UV_CONCURRENT_DOWNLOADS=4

COPY 10_async/10_temporal/110_pydantic_ai/pyproject.toml /app/110_pydantic_ai/pyproject.toml
COPY 10_async/10_temporal/110_pydantic_ai/README.md /app/110_pydantic_ai/README.md

WORKDIR /app/110_pydantic_ai

COPY 10_async/10_temporal/110_pydantic_ai/project /app/110_pydantic_ai/project
COPY 10_async/10_temporal/110_pydantic_ai/tests /app/110_pydantic_ai/tests
COPY test_utils /app/test_utils

# Retried because PyPI downloads sometimes drop mid-stream, and this uv
# version doesn't retry that error itself.
RUN for attempt in 1 2 3; do \
        uv pip install --system .[dev] && exit 0; \
        echo "uv pip install failed (attempt $attempt of 3)"; \
        [ "$attempt" -lt 3 ] && sleep $((attempt * 10)); \
    done; \
    exit 1

ENV PYTHONPATH=/app

ENV AGENT_NAME=at110-pydantic-ai

CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]

# When we deploy the worker, we will replace the CMD with the following
# CMD ["python", "-m", "run_worker"]
