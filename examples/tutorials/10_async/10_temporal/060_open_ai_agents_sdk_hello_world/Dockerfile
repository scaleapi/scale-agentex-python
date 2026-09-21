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
    nodejs \
    npm \ 
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/**

# Install tctl (Temporal CLI)
RUN curl -L https://github.com/temporalio/tctl/releases/download/v1.18.1/tctl_1.18.1_linux_arm64.tar.gz -o /tmp/tctl.tar.gz && \
    tar -xzf /tmp/tctl.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/tctl && \
    rm /tmp/tctl.tar.gz

RUN uv pip install --system --upgrade pip setuptools wheel

ENV UV_HTTP_TIMEOUT=1000

# Copy pyproject.toml and README.md to install dependencies
COPY 10_async/10_temporal/060_open_ai_agents_sdk_hello_world/pyproject.toml /app/060_open_ai_agents_sdk_hello_world/pyproject.toml
COPY 10_async/10_temporal/060_open_ai_agents_sdk_hello_world/README.md /app/060_open_ai_agents_sdk_hello_world/README.md

WORKDIR /app/060_open_ai_agents_sdk_hello_world

# Copy the project code
COPY 10_async/10_temporal/060_open_ai_agents_sdk_hello_world/project /app/060_open_ai_agents_sdk_hello_world/project

# Copy the test files
COPY 10_async/10_temporal/060_open_ai_agents_sdk_hello_world/tests /app/060_open_ai_agents_sdk_hello_world/tests

# Copy shared test utilities
COPY test_utils /app/test_utils

# Install the required Python packages with dev dependencies
RUN uv pip install --system .[dev]

WORKDIR /app/060_open_ai_agents_sdk_hello_world

ENV PYTHONPATH=/app

# Set test environment variables
ENV AGENT_NAME=at060-open-ai-agents-sdk-hello-world

# Run the ACP server using uvicorn
CMD ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]

# When we deploy the worker, we will replace the CMD with the following
# CMD ["python", "-m", "run_worker"] 
