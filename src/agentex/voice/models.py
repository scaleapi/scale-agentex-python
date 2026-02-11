"""Data models for voice agent state and responses."""

from typing import Optional

from pydantic import BaseModel, Field


class ProcessingInfo(BaseModel):
    """Processing information for distributed coordination and interruption handling.
    
    This model tracks the current message being processed to enable:
    - Interruption detection when a new message arrives
    - Prefix checking to avoid duplicate processing
    - Timeout detection for crashed processors
    """
    
    message_id: str  # Unique ID for this message processing
    message_content: str  # Content being processed (for prefix checking)
    started_at: float  # Unix timestamp
    interrupted: bool = False  # Signal to stop processing
    interrupted_by: Optional[str] = None  # ID of interrupting message


class AgentState(BaseModel):
    """Base state model for voice agent conversations.
    
    This tracks the conversation history and processing information.
    Subclass this to add agent-specific state fields.
    
    Example:
        class MyAgentState(AgentState):
            custom_field: str = "default"
            conversation_phase: str = "introduction"
    """
    
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    processing_info: Optional[ProcessingInfo] = None
    state_version: int = 0  # Increment on each successful save


class AgentResponse(BaseModel):
    """Base response model for voice agent LLM outputs.
    
    This defines the structured output format from the LLM.
    Subclass this to add agent-specific response fields.
    
    Example:
        class MyAgentResponse(AgentResponse):
            phase_transition: bool = False
            new_phase: Optional[str] = None
    """
    
    response_text: str = Field(description="The agent's response to the user")
