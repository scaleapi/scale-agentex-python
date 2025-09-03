"""
AgentPlatformWorkflow - Platform-agnostic agent workflow base class.

This provides a unified workflow base that uses the strategy pattern to execute
agents across different platforms while maintaining ACP compatibility and
Agentex's workflow conventions.
"""

from typing import Any, Dict, Optional
from temporalio import workflow
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.types.acp import CreateTaskParams, SendEventParams
from .bridge import ACPAgentBridge
from .strategies import AgentExecutionStrategy
from .registry import AgentPlatformRegistry
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

class AgentPlatformWorkflow(BaseWorkflow):
    """Platform-agnostic agent workflow with ACP integration"""
    
    # Set by subclass to specify execution strategy
    execution_strategy: Optional[AgentExecutionStrategy] = None
    
    def __init__(self):
        # Get display name from environment variables like existing workflows
        from agentex.lib.environment_variables import EnvironmentVariables
        env_vars = EnvironmentVariables.refresh()
        display_name = env_vars.AGENT_NAME if env_vars.AGENT_NAME else "Agent Platform Workflow"
        
        super().__init__(display_name)
        self._agent = None
        self._agent_config = None
        self._complete_task = False
    
    async def create_agent(self) -> Any:
        """
        Override to define platform-specific agent creation.
        
        This method should return the agent configuration dictionary
        or the agent instance itself, depending on the strategy used.
        """
        raise NotImplementedError("Must implement create_agent() in subclass")
    
    def _extract_agent_config(self) -> Dict[str, Any]:
        """
        Extract agent configuration from the created agent.
        
        This can be overridden by subclasses for custom config extraction.
        Handles serialization of complex types for Temporal activities.
        """
        if self._agent is None:
            return {}
        
        # For OpenAI Agents, we need to store the constructor arguments
        # rather than the agent instance itself
        if hasattr(self._agent, '__class__') and self._agent.__class__.__name__ == 'Agent':
            # Extract OpenAI Agent constructor parameters
            config = {}
            for attr in ['name', 'model', 'instructions', 'tools', 'handoffs', 'handoff_description']:
                if hasattr(self._agent, attr):
                    value = getattr(self._agent, attr)
                    config[attr] = value
            
            # Handle model_settings specially - ensure it's serializable
            if hasattr(self._agent, 'model_settings') and self._agent.model_settings:
                model_settings = self._agent.model_settings
                if hasattr(model_settings, 'model_dump'):
                    config['model_settings'] = model_settings.model_dump()
                elif hasattr(model_settings, '__dict__'):
                    config['model_settings'] = vars(model_settings)
                else:
                    config['model_settings'] = model_settings
            
            return config
        
        # If agent is already a config dict, return it
        if isinstance(self._agent, dict):
            return self._agent
        
        # If agent has a model_dump method (Pydantic model), use it
        if hasattr(self._agent, 'model_dump'):
            return self._agent.model_dump()
        
        # If agent has dict method, use it
        if hasattr(self._agent, '__dict__'):
            return vars(self._agent)
        
        # Fallback: assume agent can be stringified for basic config
        return {"agent": str(self._agent)}
    
    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> None:
        """
        ACP task creation handler - initializes agent and waits for completion.
        
        This follows the Agentex workflow pattern with @workflow.run decorator.
        """
        try:
            # Initialize execution strategy if not set
            if self.execution_strategy is None:
                raise RuntimeError("execution_strategy must be set in subclass")
            
            # Initialize agent on task creation
            logger.debug(f"Initializing agent for task: {params.task.id}")
            self._agent = await self.create_agent()
            self._agent_config = self._extract_agent_config()
            
            logger.info(f"Agent initialized for task {params.task.id} using {self.execution_strategy.platform_name} platform")
            
            # Wait for task completion
            await workflow.wait_condition(lambda: self._complete_task)
            
        except Exception as e:
            logger.error(f"Task creation failed for {params.task.id}: {e}")
            raise
    
    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """
        ACP event handler - uses strategy pattern for platform-agnostic execution.
        
        This processes incoming events and executes the agent using the
        configured strategy, then sends responses back via ACP.
        """
        try:
            # Ensure agent is initialized
            if not self._agent:
                logger.warning(f"Agent not initialized for task {params.task.id}, initializing now")
                self._agent = await self.create_agent()
                self._agent_config = self._extract_agent_config()
            
            # Extract user input from ACP event
            user_input, author = ACPAgentBridge.extract_user_input_from_event(params.event)
            
            if not user_input.strip():
                logger.warning(f"Empty input received for task {params.task.id}")
                await ACPAgentBridge.agent_output_to_acp_message(
                    "I received an empty message. Please provide some input.",
                    params.task.id
                )
                return
            
            logger.debug(f"Processing event for task {params.task.id} from {author}: {user_input[:100]}...")
            
            # Platform-agnostic execution via strategy
            result = await self.execution_strategy.execute_agent(
                agent_config=self._agent_config,
                user_input=user_input,
                task_id=params.task.id,
                trace_id=params.task.id  # Use task ID as trace ID
            )
            
            # Send response via ACP protocol
            await ACPAgentBridge.agent_output_to_acp_message(
                output=result,
                task_id=params.task.id,
                author="agent"
            )
            
            logger.debug(f"Successfully processed event for task {params.task.id}")
            
        except Exception as e:
            logger.error(f"Event processing failed for task {params.task.id}: {e}")
            
            # Send error message via ACP
            try:
                error_message = f"I encountered an error while processing your request: {str(e)}"
                await ACPAgentBridge.agent_output_to_acp_message(
                    output=error_message,
                    task_id=params.task.id,
                    author="agent"
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message for task {params.task.id}: {send_error}")
            
            # Re-raise for workflow error handling
            raise
    
    def complete_task(self) -> None:
        """Mark task as complete to end the workflow"""
        self._complete_task = True
        logger.debug("Task marked as complete")


# Convenience base classes for specific platforms

class OpenAIAgentWorkflow(AgentPlatformWorkflow):
    """Convenience base class for OpenAI agent workflows"""
    
    def __init__(self):
        super().__init__()
        self.execution_strategy = AgentPlatformRegistry.get_strategy("openai")
    
    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> None:
        """Task creation handler - delegates to platform base class"""
        await super().on_task_create(params)


class LangChainAgentWorkflow(AgentPlatformWorkflow):
    """Convenience base class for LangChain agent workflows (future)"""
    
    def __init__(self):
        super().__init__()
        self.execution_strategy = AgentPlatformRegistry.get_strategy("langchain")


class CrewAIAgentWorkflow(AgentPlatformWorkflow):
    """Convenience base class for CrewAI agent workflows (future)"""
    
    def __init__(self):
        super().__init__()
        self.execution_strategy = AgentPlatformRegistry.get_strategy("crewai")
