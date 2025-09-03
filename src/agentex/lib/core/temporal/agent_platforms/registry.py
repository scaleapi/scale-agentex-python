"""
Agent Platform Registry - Registry for available agent execution strategies.

This provides a central registry for managing different agent platform strategies,
allowing dynamic selection and registration of execution strategies for different
agent frameworks.
"""

from typing import Dict, Type
from .strategies import (
    AgentExecutionStrategy, 
    OpenAIExecutionStrategy, 
    LangChainExecutionStrategy, 
    CrewAIExecutionStrategy
)
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

class AgentPlatformRegistry:
    """Registry for available agent execution strategies"""
    
    _strategies: Dict[str, Type[AgentExecutionStrategy]] = {
        "openai": OpenAIExecutionStrategy,
        "langchain": LangChainExecutionStrategy,  # Future
        "crewai": CrewAIExecutionStrategy,        # Future
    }
    
    @classmethod
    def get_strategy(cls, platform_name: str) -> AgentExecutionStrategy:
        """
        Get execution strategy for a platform.
        
        Args:
            platform_name: Name of the platform ("openai", "langchain", etc.)
            
        Returns:
            AgentExecutionStrategy: Instantiated strategy for the platform
            
        Raises:
            ValueError: If platform is not supported
        """
        if platform_name not in cls._strategies:
            available = ", ".join(cls._strategies.keys())
            raise ValueError(f"Unsupported platform: {platform_name}. Available: {available}")
        
        strategy_class = cls._strategies[platform_name]
        strategy_instance = strategy_class()
        
        logger.debug(f"Created execution strategy for platform: {platform_name}")
        return strategy_instance
    
    @classmethod
    def register_platform(
        cls, 
        name: str, 
        strategy_class: Type[AgentExecutionStrategy]
    ) -> None:
        """
        Register a new agent platform strategy.
        
        Args:
            name: Platform name to register
            strategy_class: Strategy class implementing AgentExecutionStrategy
        """
        if not issubclass(strategy_class, AgentExecutionStrategy):
            raise ValueError("Strategy class must implement AgentExecutionStrategy")
        
        cls._strategies[name] = strategy_class
        logger.info(f"Registered agent platform: {name}")
    
    @classmethod
    def get_available_platforms(cls) -> list[str]:
        """
        Get list of available platform names.
        
        Returns:
            list[str]: List of available platform names
        """
        return list(cls._strategies.keys())
    
    @classmethod
    def is_platform_available(cls, platform_name: str) -> bool:
        """
        Check if a platform is available.
        
        Args:
            platform_name: Name of the platform to check
            
        Returns:
            bool: True if platform is available
        """
        return platform_name in cls._strategies
