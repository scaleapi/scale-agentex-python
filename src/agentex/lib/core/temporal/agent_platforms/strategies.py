"""
Agent execution strategies - pluggable implementations for different agent frameworks.

This module provides the strategy pattern implementation for executing agents across
different platforms (OpenAI Agents SDK, LangChain, CrewAI, etc.) while maintaining
a unified interface for Agentex workflows.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

class AgentExecutionStrategy(ABC):
    """Abstract base class for platform-specific agent execution"""
    
    @abstractmethod
    async def execute_agent(
        self, 
        agent_config: Dict[str, Any], 
        user_input: str,
        task_id: str,
        trace_id: str = None
    ) -> str:
        """
        Execute agent using platform-specific logic.
        
        Args:
            agent_config: Platform-specific agent configuration
            user_input: User input to process
            task_id: Task ID for tracing and context
            trace_id: Optional trace ID for observability
            
        Returns:
            str: Agent's response output
        """
        pass
    
    @abstractmethod
    async def create_agent_from_config(self, config: Dict[str, Any]) -> Any:
        """
        Create platform-specific agent instance from configuration.
        
        Args:
            config: Agent configuration dictionary
            
        Returns:
            Any: Platform-specific agent instance
        """
        pass
    
    @abstractmethod
    def get_worker_config(self, platform_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get platform-specific Temporal worker configuration.
        
        Args:
            platform_config: Platform-specific configuration
            
        Returns:
            Dict[str, Any]: Worker configuration overrides
        """
        pass
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name for this strategy"""
        pass


class OpenAIExecutionStrategy(AgentExecutionStrategy):
    """OpenAI Agents SDK execution strategy"""
    
    def __init__(self):
        from agentex.lib.core.services.adk.providers.openai import OpenAIService
        self.openai_service = OpenAIService()
    
    @property
    def platform_name(self) -> str:
        return "openai"
    
    async def execute_agent(
        self, 
        agent_config: Dict[str, Any], 
        user_input: str,
        task_id: str,
        trace_id: str = None
    ) -> str:
        """
        Execute OpenAI agent using direct Agent SDK integration.
        
        This bypasses the existing run_agent_streamed_auto_send activity to use
        the OpenAI Agents SDK directly for better performance and durability.
        """
        try:
            # Import OpenAI Agents SDK
            from agents import Agent, Runner
            
            # Create agent from config
            agent = Agent(**agent_config)
            
            # Execute agent with user input
            logger.debug(f"Executing OpenAI agent for task {task_id} with input: {user_input[:100]}...")
            result = await Runner.run(starting_agent=agent, input=user_input)
            
            # Extract final output
            output = result.final_output if hasattr(result, 'final_output') else str(result)
            
            logger.debug(f"OpenAI agent execution completed for task {task_id}")
            return output
            
        except ImportError as e:
            logger.error(f"OpenAI Agents SDK not available: {e}")
            raise RuntimeError("OpenAI Agents SDK is required for OpenAI strategy") from e
        except Exception as e:
            logger.error(f"OpenAI agent execution failed for task {task_id}: {e}")
            raise
    
    async def create_agent_from_config(self, config: Dict[str, Any]) -> Any:
        """Create OpenAI Agent instance from configuration"""
        try:
            from agents import Agent
            return Agent(**config)
        except ImportError as e:
            logger.error(f"OpenAI Agents SDK not available: {e}")
            raise RuntimeError("OpenAI Agents SDK is required for OpenAI strategy") from e
    
    def get_worker_config(self, platform_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get OpenAI-specific worker configuration.
        
        This includes proper OpenAI plugin integration with data converters,
        interceptors, and other Temporal worker settings specific to OpenAI agents.
        """
        config = {}
        
        # Configure OpenAI plugin with proper integration
        if platform_config.get("enable_openai_plugin", False):
            try:
                from temporalio.contrib.openai_agents import (
                    OpenAIAgentsPlugin, 
                    ModelActivityParameters,
                    ChatCompletionActivity
                )
                
                # Configure plugin with model parameters
                plugin_config = {}
                if "model_timeout" in platform_config:
                    plugin_config["default_timeout"] = platform_config["model_timeout"]
                
                plugin = OpenAIAgentsPlugin(**plugin_config)
                config["plugins"] = [plugin]
                
                # Add OpenAI-specific data converters for better serialization
                # This ensures OpenAI types are properly handled in Temporal
                config["data_converter"] = self._create_openai_data_converter()
                
                logger.info("OpenAI Temporal plugin enabled with full integration")
                
            except ImportError as e:
                logger.warning(f"OpenAI Temporal plugin not available ({e}), using direct integration")
        
        # Add interceptors for OpenAI-specific features
        if platform_config.get("enable_interceptors", True):
            config["interceptors"] = self._create_openai_interceptors(platform_config)
        
        return config
    
    def _create_openai_data_converter(self):
        """Create OpenAI-optimized data converter for Temporal serialization"""
        try:
            from temporalio.converter import CompositePayloadConverter, DataConverter
            from temporalio.contrib.openai_agents import OpenAIPayloadConverter
            
            # Use OpenAI-specific payload converter for better type handling
            return DataConverter(
                payload_converter_class=CompositePayloadConverter([
                    OpenAIPayloadConverter(),
                    *DataConverter.default.payload_converter.converters
                ])
            )
        except ImportError:
            logger.debug("OpenAI payload converter not available, using default")
            return None
    
    def _create_openai_interceptors(self, platform_config: Dict[str, Any]) -> list:
        """Create OpenAI-specific workflow interceptors"""
        interceptors = []
        
        # Add timeout interceptor for OpenAI calls
        if platform_config.get("model_timeout"):
            try:
                from temporalio.contrib.openai_agents import OpenAITimeoutInterceptor
                interceptors.append(
                    OpenAITimeoutInterceptor(timeout=platform_config["model_timeout"])
                )
            except ImportError:
                logger.debug("OpenAI timeout interceptor not available")
        
        # Add retry interceptor for OpenAI API resilience  
        if platform_config.get("enable_retries", True):
            try:
                from temporalio.contrib.openai_agents import OpenAIRetryInterceptor
                interceptors.append(OpenAIRetryInterceptor())
            except ImportError:
                logger.debug("OpenAI retry interceptor not available")
        
        return interceptors


# Future strategy implementations for other platforms

class LangChainExecutionStrategy(AgentExecutionStrategy):
    """LangChain execution strategy (future implementation)"""
    
    @property
    def platform_name(self) -> str:
        return "langchain"
    
    async def execute_agent(self, agent_config: Dict[str, Any], user_input: str, task_id: str, trace_id: str = None) -> str:
        # TODO: Implement LangChain agent execution
        raise NotImplementedError("LangChain strategy not yet implemented")
    
    async def create_agent_from_config(self, config: Dict[str, Any]) -> Any:
        # TODO: Implement LangChain agent creation
        raise NotImplementedError("LangChain strategy not yet implemented")
    
    def get_worker_config(self, platform_config: Dict[str, Any]) -> Dict[str, Any]:
        return {}


class CrewAIExecutionStrategy(AgentExecutionStrategy):
    """CrewAI execution strategy (future implementation)"""
    
    @property
    def platform_name(self) -> str:
        return "crewai"
    
    async def execute_agent(self, agent_config: Dict[str, Any], user_input: str, task_id: str, trace_id: str = None) -> str:
        # TODO: Implement CrewAI agent execution  
        raise NotImplementedError("CrewAI strategy not yet implemented")
    
    async def create_agent_from_config(self, config: Dict[str, Any]) -> Any:
        # TODO: Implement CrewAI agent creation
        raise NotImplementedError("CrewAI strategy not yet implemented")
    
    def get_worker_config(self, platform_config: Dict[str, Any]) -> Dict[str, Any]:
        return {}
