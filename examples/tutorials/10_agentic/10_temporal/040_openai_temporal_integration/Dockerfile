# Use the official Agentex base image
FROM agentex-base:latest

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY 040_openai_temporal_integration/pyproject.toml ./
RUN pip install -e .

# Copy the agent code
COPY 040_openai_temporal_integration/ ./

# Set environment variables
ENV PYTHONPATH=/app
ENV WORKFLOW_NAME=at040-openai-temporal-integration
ENV WORKFLOW_TASK_QUEUE=040_openai_temporal_integration_queue
ENV AGENT_NAME=at040-openai-temporal-integration

# Expose the default ACP port
EXPOSE 8000

# Default command to run the worker
CMD ["python", "project/run_worker.py"]
