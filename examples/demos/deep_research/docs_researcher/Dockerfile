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
    build-essential \
    gcc \
    cmake \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/**

# Install tctl (Temporal CLI)
RUN curl -L https://github.com/temporalio/tctl/releases/download/v1.18.1/tctl_1.18.1_linux_arm64.tar.gz -o /tmp/tctl.tar.gz && \
    tar -xzf /tmp/tctl.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/tctl && \
    rm /tmp/tctl.tar.gz

RUN uv pip install --system --upgrade pip setuptools wheel

ENV UV_HTTP_TIMEOUT=1000

COPY deep_research/docs_researcher/pyproject.toml /app/docs_researcher/pyproject.toml

WORKDIR /app/docs_researcher

COPY deep_research/docs_researcher/project /app/docs_researcher/project

RUN uv pip install --system .

ENV PYTHONPATH=/app
ENV AGENT_NAME=deep-research-docs

CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]
