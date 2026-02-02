"""Guardrail system for voice agents.

This module provides base classes for implementing guardrails that check
user messages for policy violations, inappropriate content, or off-topic discussions.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional

from agentex.lib import adk
from agentex.lib.utils.logging import make_logger
from agents import OpenAIChatCompletionsModel
from pydantic import BaseModel, Field

from agentex.voice.models import AgentState

logger = make_logger(__name__)


# ============================================================================
# Guardrail Response Models
# ============================================================================


class GuardrailResponse(BaseModel):
    """Structured response for guardrail checks."""
    
    pass_: bool = Field(alias="pass", description="Whether the check passed")
    reason: str = Field(description="Brief explanation of the decision")


# ============================================================================
# Base Guardrail Classes
# ============================================================================


class Guardrail(ABC):
    """Abstract base class for guardrails.
    
    Guardrails are checks that run on user messages to enforce policies,
    detect inappropriate content, or guide conversations back on track.
    
    When a guardrail fails:
    1. The agent stops processing the normal LLM response
    2. The guardrail's outcome_prompt is used instead
    3. The agent responds with the guardrail-specific message
    
    Example:
        class MyGuardrail(Guardrail):
            def __init__(self):
                super().__init__(
                    name="my_guardrail",
                    outcome_prompt="Sorry, I can't help with that."
                )
            
            async def check(self, user_message, conversation_state):
                # Return True if passed, False if failed
                return "bad_word" not in user_message.lower()
    """
    
    def __init__(
        self,
        name: str,
        outcome_prompt: Optional[str] = None,
        outcome_prompt_file: Optional[str] = None,
    ):
        """Initialize the guardrail.
        
        Args:
            name: Unique identifier for this guardrail
            outcome_prompt: Message to display when guardrail fails
            outcome_prompt_file: Path to file containing outcome prompt
        
        Raises:
            ValueError: If neither outcome_prompt nor outcome_prompt_file is provided
            FileNotFoundError: If outcome_prompt_file doesn't exist
        """
        self.name = name
        if outcome_prompt is None and outcome_prompt_file is None:
            raise ValueError("Either outcome_prompt or outcome_prompt_file must be provided.")

        if outcome_prompt is not None:
            self.outcome_prompt = outcome_prompt
        else:
            # Load from file
            if not os.path.exists(outcome_prompt_file):
                raise FileNotFoundError(f"Outcome prompt file not found: {outcome_prompt_file}")
            
            with open(outcome_prompt_file, "r") as f:
                self.outcome_prompt = f.read()

    @abstractmethod
    async def check(self, user_message: str, conversation_state: AgentState) -> bool:
        """Check if the user message passes this guardrail.
        
        Args:
            user_message: The user's input message
            conversation_state: Current conversation state
        
        Returns:
            True if the message passes this guardrail, False otherwise
        """
        pass


class LLMGuardrail(Guardrail):
    """Base class for LLM-based guardrails that use prompts and structured output.
    
    This class provides a pattern for implementing guardrails that:
    1. Use an LLM to classify whether a message violates a policy
    2. Return structured GuardrailResponse with pass/fail and reasoning
    3. Load prompts from Jinja2 templates
    4. Support context-specific customization
    
    Subclasses should define:
    - name: Unique identifier for the guardrail
    - outcome_prompt: Message to display when guardrail fails
    - prompt_template: Path to Jinja2 template file (.j2)
    - model: Optional LLM model to use
    
    Example:
        class MedicalAdviceGuardrail(LLMGuardrail):
            def __init__(self):
                super().__init__(
                    name="medical_advice",
                    outcome_prompt="I can't provide medical advice. Please consult your doctor.",
                    prompt_template="prompts/medical_advice_check.j2",
                    model="vertex_ai/gemini-2.5-flash-lite",
                )
    
    The prompt template receives these variables:
    - user_message: The current user message
    - previous_assistant_message: The last agent message (if any)
    - Any additional kwargs passed to __init__
    """
    
    def __init__(
        self,
        name: str,
        outcome_prompt: str,
        prompt_template: str,
        model: str = "vertex_ai/gemini-2.5-flash-lite",
        openai_client = None,
        **template_kwargs,
    ):
        """Initialize LLM-based guardrail.
        
        Args:
            name: Unique identifier for the guardrail
            outcome_prompt: Message to display when guardrail fails
            prompt_template: Path to Jinja2 template file (.j2) for the check prompt
            model: LLM model to use for classification
            openai_client: OpenAI-compatible client (defaults to adk default)
            **template_kwargs: Additional variables to pass to the prompt template
        """
        super().__init__(name=name, outcome_prompt=outcome_prompt)
        self.prompt_template = prompt_template
        self.model = model
        self.openai_client = openai_client
        self.template_kwargs = template_kwargs

    async def check(self, user_message: str, conversation_state: AgentState) -> bool:
        """Check if the message passes this guardrail using LLM classification.
        
        Args:
            user_message: The user's input message
            conversation_state: Current conversation state
        
        Returns:
            True if the message passes, False otherwise
        
        Raises:
            Exception: If LLM call fails
        """
        # Extract previous assistant message for context (if available)
        latest_assistant_message = None
        assistant_messages = [
            msg for msg in conversation_state.conversation_history if msg["role"] == "assistant"
        ]
        if assistant_messages:
            latest_assistant_message = assistant_messages[-1]["content"]

        # Load and render the prompt template
        # Note: Subclasses should implement their own prompt loading logic
        # or use agentex.lib.utils.jinja helpers
        prompt = self._load_prompt(
            user_message=user_message,
            previous_assistant_message=latest_assistant_message,
            **self.template_kwargs
        )
        
        agent_instructions = self._get_agent_instructions()

        try:
            # Call LLM with structured output
            result = await adk.providers.openai.run_agent(
                input_list=[{"role": "user", "content": prompt}],
                mcp_server_params=[],
                agent_name=f"guardrail_{self.name}",
                agent_instructions=agent_instructions,
                model=OpenAIChatCompletionsModel(model=self.model, openai_client=self.openai_client),
                tools=[],
                output_type=GuardrailResponse,
            )
            # Parse the response
            response = result.final_output

            # Log the guardrail check result
            logger.info(
                f"Guardrail '{self.name}' check - Pass: {response.pass_} - Reason: {response.reason}"
            )

            return response.pass_

        except Exception as e:
            logger.error(f"Guardrail '{self.name}' LLM call failed: {e}", exc_info=True)
            raise e
    
    def _load_prompt(self, user_message: str, previous_assistant_message: Optional[str], **kwargs) -> str:
        """Load and render the prompt template.
        
        This is a placeholder method. Subclasses should override this
        to implement their own prompt loading logic using Jinja2.
        
        Args:
            user_message: The current user message
            previous_assistant_message: The last agent message (if any)
            **kwargs: Additional template variables
        
        Returns:
            Rendered prompt string
        """
        # Default implementation - subclasses should override
        return f"""
Evaluate if this user message violates the {self.name} policy:

User message: {user_message}

Previous assistant message: {previous_assistant_message or "None"}

Respond with a JSON object containing:
- "pass": true if the message is acceptable, false if it violates the policy
- "reason": brief explanation of your decision
"""
    
    def _get_agent_instructions(self) -> str:
        """Get the agent instructions for the guardrail LLM.
        
        Subclasses can override this to provide custom instructions.
        
        Returns:
            Agent instructions string
        """
        return f"""You are a policy compliance classifier for the {self.name} guardrail.

Evaluate the user's message and determine if it passes or fails the policy check.

Respond ONLY with valid JSON matching this schema:
{{
    "pass": true/false,
    "reason": "brief explanation"
}}

Be objective and consistent in your evaluations."""


# ============================================================================
# Example Guardrail Implementations
# ============================================================================


class SampleMedicalEmergencyGuardrail(Guardrail):
    """Example guardrail that checks for medical emergency mentions.
    
    This is a simple keyword-based example. Production implementations
    should use LLMGuardrail for more sophisticated detection.
    """
    
    def __init__(self):
        super().__init__(
            name="medical_emergency",
            outcome_prompt="If you're experiencing a medical emergency, please call 911 or your local emergency services immediately.",
        )

    async def check(self, user_message: str, conversation_state: AgentState) -> bool:
        """Check if the message contains emergency keywords.
        
        Args:
            user_message: The user's input message
            conversation_state: Current conversation state
        
        Returns:
            True if no emergency detected, False if emergency keywords found
        """
        emergency_keywords = ["emergency", "911", "ambulance", "can't breathe"]
        message_lower = user_message.lower()
        
        for keyword in emergency_keywords:
            if keyword in message_lower:
                logger.warning(f"Medical emergency keyword detected: {keyword}")
                return False
        
        return True
