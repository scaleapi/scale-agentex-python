"""
Agent Selection and Discovery for AgentEx Testing Framework.

Provides robust agent filtering and selection with proper validation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentex.types import Agent

from agentex.lib.testing.exceptions import AgentNotFoundError, AgentSelectionError

logger = logging.getLogger(__name__)


class AgentSelector:
    """Handles agent discovery and selection for testing."""

    @staticmethod
    def _validate_agent(agent: Agent) -> bool:
        """
        Validate that agent object has required attributes.

        Args:
            agent: Agent object to validate

        Returns:
            True if agent is valid, False otherwise
        """
        if agent is None:
            return False

        # Check required attributes
        required_attrs = ["id", "acp_type"]
        for attr in required_attrs:
            if not hasattr(agent, attr):
                logger.debug(f"Agent missing required attribute: {attr}")
                return False

        return True

    @staticmethod
    def _get_agent_name(agent: Agent) -> str:
        """
        Safely get agent name with fallback to ID.

        Args:
            agent: Agent object

        Returns:
            Agent name or ID if name not available
        """
        if hasattr(agent, "name") and agent.name:
            return str(agent.name)
        return str(agent.id)

    @classmethod
    def _filter_agents(
        cls,
        agents: list[Agent],
        acp_type: str,
        agent_name: str | None = None,
        agent_id: str | None = None,
    ) -> list[Agent]:
        """
        Filter agents by type and optional name/ID.

        Args:
            agents: List of all available agents
            acp_type: Agent type to filter by (e.g., "sync", "agentic")
            agent_name: Optional agent name to match
            agent_id: Optional agent ID to match

        Returns:
            List of matching agents
        """
        # First validate all agents
        valid_agents = [a for a in agents if cls._validate_agent(a)]

        if len(valid_agents) < len(agents):
            logger.warning(f"Filtered out {len(agents) - len(valid_agents)} invalid agents")

        # Filter by ACP type
        type_matches = [a for a in valid_agents if a.acp_type == acp_type]

        # Filter by ID if specified
        if agent_id:
            type_matches = [a for a in type_matches if a.id == agent_id]

        # Filter by name if specified
        if agent_name:
            type_matches = [a for a in type_matches if cls._get_agent_name(a) == agent_name]

        return type_matches

    @classmethod
    def select_sync_agent(
        cls,
        agents: list[Agent],
        agent_name: str | None = None,
        agent_id: str | None = None,
    ) -> Agent:
        """
        Select a sync agent for testing.

        **Agent selection is always required** - you must specify either agent_name or agent_id.

        Args:
            agents: List of all available agents
            agent_name: Agent name to select (required if agent_id not provided)
            agent_id: Agent ID to select (required if agent_name not provided)

        Returns:
            Selected sync agent

        Raises:
            AgentNotFoundError: No matching agents found
            AgentSelectionError: Agent selection required or multiple agents match
        """
        # First, get all agents of the correct type
        type_matches = [a for a in agents if cls._validate_agent(a) and a.acp_type == "sync"]

        # ALWAYS require explicit selection
        if agent_name is None and agent_id is None:
            agent_names = [cls._get_agent_name(a) for a in type_matches]
            raise AgentSelectionError(
                "sync",
                agent_names,
                message="Agent selection required. Specify agent_name or agent_id parameter.",
            )

        # Now filter by name/ID
        matching_agents = cls._filter_agents(agents, "sync", agent_name, agent_id)

        if not matching_agents:
            raise AgentNotFoundError("sync", agent_name, agent_id)

        if len(matching_agents) > 1:
            # Multiple matches - need user to be more specific
            agent_names = [cls._get_agent_name(a) for a in matching_agents]
            raise AgentSelectionError("sync", agent_names)

        selected = matching_agents[0]
        logger.info(f"Selected sync agent: {cls._get_agent_name(selected)} (id: {selected.id})")
        return selected

    @classmethod
    def select_agentic_agent(
        cls,
        agents: list[Agent],
        agent_name: str | None = None,
        agent_id: str | None = None,
    ) -> Agent:
        """
        Select an agentic agent for testing.

        **Agent selection is always required** - you must specify either agent_name or agent_id.

        Args:
            agents: List of all available agents
            agent_name: Agent name to select (required if agent_id not provided)
            agent_id: Agent ID to select (required if agent_name not provided)

        Returns:
            Selected agentic agent

        Raises:
            AgentNotFoundError: No matching agents found
            AgentSelectionError: Agent selection required or multiple agents match
        """
        # First, get all agents of the correct type
        type_matches = [a for a in agents if cls._validate_agent(a) and a.acp_type == "agentic"]

        # ALWAYS require explicit selection
        if agent_name is None and agent_id is None:
            agent_names = [cls._get_agent_name(a) for a in type_matches]
            raise AgentSelectionError(
                "agentic",
                agent_names,
                message="Agent selection required. Specify agent_name or agent_id parameter.",
            )

        # Now filter by name/ID
        matching_agents = cls._filter_agents(agents, "agentic", agent_name, agent_id)

        if not matching_agents:
            raise AgentNotFoundError("agentic", agent_name, agent_id)

        if len(matching_agents) > 1:
            # Multiple matches - need user to be more specific
            agent_names = [cls._get_agent_name(a) for a in matching_agents]
            raise AgentSelectionError("agentic", agent_names)

        selected = matching_agents[0]
        logger.info(f"Selected agentic agent: {cls._get_agent_name(selected)} (id: {selected.id})")
        return selected
