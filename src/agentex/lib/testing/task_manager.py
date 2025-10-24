"""
Task Lifecycle Management for Testing.

Provides centralized task creation and cleanup with proper error handling.
"""

from __future__ import annotations

import uuid
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentex import Agentex, AsyncAgentex
    from agentex.types import Task, Agent

from agentex.lib.testing.config import config
from agentex.lib.testing.exceptions import TaskCleanupError

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages test task lifecycle with proper cleanup."""

    @staticmethod
    def generate_task_name(task_type: str) -> str:
        """
        Generate unique task name for testing.

        Args:
            task_type: Type of task (e.g., "sync", "agentic")

        Returns:
            Unique task name with prefix
        """
        task_id = uuid.uuid4().hex[:8]
        return f"{config.task_name_prefix}-{task_type}-{task_id}"

    @staticmethod
    def create_task_sync(client: Agentex, agent_id: str, task_type: str) -> Task:
        """
        Create a test task (sync version).

        Args:
            client: Sync Agentex client
            agent_id: Agent ID to create task for
            task_type: Task type for naming

        Returns:
            Created task
        """
        from agentex.types.agent_rpc_params import ParamsCreateTaskRequest

        task_name = TaskManager.generate_task_name(task_type)
        logger.debug(f"Creating task: {task_name} for agent {agent_id}")

        params = ParamsCreateTaskRequest(name=task_name, params={})
        task = client.agents.create_task(agent_id=agent_id, params=params)

        logger.debug(f"Task created successfully: {task.id}")
        return task

    @staticmethod
    async def create_task_async(client: AsyncAgentex, agent: Agent, task_type: str) -> Task:
        """
        Create a test task (async version).

        Args:
            client: Async Agentex client
            agent: Agent object (needs name for API call)
            task_type: Task type for naming

        Returns:
            Created task
        """
        from agentex.types.agent_rpc_params import ParamsCreateTaskRequest

        task_name = TaskManager.generate_task_name(task_type)
        logger.debug(f"Creating task: {task_name} for agent {agent.name}")

        params = ParamsCreateTaskRequest(name=task_name, params={})

        # Use agent.name for the API call (required by AgentEx API)
        agent_name = agent.name if hasattr(agent, "name") and agent.name else agent.id

        response = await client.agents.create_task(agent_name=agent_name, params=params)

        # Extract task from response.result
        if hasattr(response, "result") and response.result:
            task = response.result
            logger.debug(f"Task created successfully: {task.id}")
            return task
        else:
            raise Exception(f"Failed to create task: {response}")

    @staticmethod
    def cleanup_task_sync(client: Agentex, task_id: str, warn_on_failure: bool = True) -> None:
        """
        Cleanup test task (sync version).

        Args:
            client: Sync Agentex client
            task_id: Task ID to cleanup
            warn_on_failure: Whether to log warnings on cleanup failure

        Raises:
            TaskCleanupError: If cleanup fails and warn_on_failure is False
        """
        try:
            logger.debug(f"Cleaning up task: {task_id}")
            client.tasks.delete(task_id=task_id)
            logger.debug(f"Task cleaned up successfully: {task_id}")
        except Exception as e:
            if warn_on_failure:
                logger.warning(f"Failed to cleanup task {task_id}: {e}")
            else:
                raise TaskCleanupError(task_id, e) from e

    @staticmethod
    async def cleanup_task_async(client: AsyncAgentex, task_id: str, warn_on_failure: bool = True) -> None:
        """
        Cleanup test task (async version).

        Args:
            client: Async Agentex client
            task_id: Task ID to cleanup
            warn_on_failure: Whether to log warnings on cleanup failure

        Raises:
            TaskCleanupError: If cleanup fails and warn_on_failure is False
        """
        try:
            logger.debug(f"Cleaning up task: {task_id}")
            await client.tasks.delete(task_id=task_id)
            logger.debug(f"Task cleaned up successfully: {task_id}")
        except Exception as e:
            if warn_on_failure:
                logger.warning(f"Failed to cleanup task {task_id}: {e}")
            else:
                raise TaskCleanupError(task_id, e) from e
