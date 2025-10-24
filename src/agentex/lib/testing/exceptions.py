"""
Custom exceptions for AgentEx Testing Framework.

Provides specific error types for better error handling and debugging.
"""
from __future__ import annotations


class AgentexTestingError(Exception):
    """Base exception for all AgentEx testing framework errors."""

    pass


class InfrastructureError(AgentexTestingError):
    """Raised when AgentEx infrastructure is unavailable or unhealthy."""

    def __init__(self, base_url: str, details: str | None = None):
        self.base_url = base_url
        message = f"AgentEx infrastructure not available at {base_url}"
        if details:
            message += f": {details}"
        message += "\n\nTroubleshooting:\n"
        message += f"  1. Check if AgentEx is running: curl {base_url}/healthz\n"
        message += "  2. Run 'make dev' to start AgentEx services\n"
        message += f"  3. Set AGENTEX_BASE_URL if using different endpoint"
        super().__init__(message)


class AgentNotFoundError(AgentexTestingError):
    """Raised when no agents matching the criteria are found."""

    def __init__(self, acp_type: str, agent_name: str | None = None, agent_id: str | None = None):
        self.acp_type = acp_type
        self.agent_name = agent_name
        self.agent_id = agent_id

        if agent_name:
            message = f"No {acp_type} agent found with name '{agent_name}'"
        elif agent_id:
            message = f"No {acp_type} agent found with ID '{agent_id}'"
        else:
            message = f"No {acp_type} agents registered"

        message += f"\n\nTroubleshooting:\n"
        message += f"  1. Run a {acp_type} agent (check tutorials for examples)\n"
        message += "  2. Verify agent is registered: agentex agents list\n"
        message += "  3. Check agent ACP type matches expected type"

        super().__init__(message)


class AgentSelectionError(AgentexTestingError):
    """Raised when agent selection is ambiguous or missing."""

    def __init__(self, acp_type: str, available_agents: list[str], message: str | None = None):
        self.acp_type = acp_type
        self.available_agents = available_agents

        if message:
            # Custom message provided (e.g., "selection required")
            error_message = f"{message}\n\n"
        else:
            # Default message for multiple agents
            error_message = f"Multiple {acp_type} agents found. Please specify which one to test.\n\n"

        error_message += f"Available {acp_type} agents:\n"
        for agent_name in available_agents:
            error_message += f"  - {agent_name}\n"
        error_message += "\nSpecify agent with:\n"
        error_message += "  test_sync_agent(agent_name='your-agent')\n"
        error_message += "  test_agentic_agent(agent_name='your-agent')\n\n"
        error_message += "To discover agent names, run: agentex agents list"

        super().__init__(error_message)


class AgentResponseError(AgentexTestingError):
    """Raised when agent response is invalid or missing."""

    def __init__(self, agent_id: str, details: str):
        self.agent_id = agent_id
        message = f"Invalid response from agent {agent_id}: {details}\n\n"
        message += "Troubleshooting:\n"
        message += "  1. Check agent logs for errors\n"
        message += "  2. Verify agent is running and healthy\n"
        message += "  3. Check AgentEx server logs"
        super().__init__(message)


class AgentTimeoutError(AgentexTestingError):
    """Raised when agent doesn't respond within timeout period."""

    def __init__(self, agent_id: str, timeout_seconds: float, task_id: str | None = None):
        self.agent_id = agent_id
        self.timeout_seconds = timeout_seconds
        self.task_id = task_id

        message = f"Agent {agent_id} did not respond within {timeout_seconds}s"
        if task_id:
            message += f" (task: {task_id})"

        message += "\n\nTroubleshooting:\n"
        message += "  1. Increase timeout: send_event(timeout_seconds=30.0)\n"
        message += "  2. Check agent logs for processing errors\n"
        message += "  3. Verify agent worker is running\n"
        message += "  4. Check Temporal workflow status if using temporal agent"

        super().__init__(message)


class TaskCleanupError(AgentexTestingError):
    """Raised when task cleanup fails."""

    def __init__(self, task_id: str, error: Exception):
        self.task_id = task_id
        self.original_error = error
        message = f"Failed to cleanup task {task_id}: {error}"
        super().__init__(message)
