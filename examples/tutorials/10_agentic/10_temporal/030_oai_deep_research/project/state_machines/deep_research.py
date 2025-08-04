from enum import Enum
from typing import Dict, List, Optional, override
from pydantic import BaseModel
from agentex.lib.sdk.state_machine import StateMachine
from agentex.types.span import Span

class DeepResearchState(str, Enum):
    TRIAGE = "triage"
    CLARIFYING = "clarifying"
    INSTRUCTION_BUILDING = "instruction_building"
    RESEARCHING = "researching"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"

class Clarifications(BaseModel):
    questions: List[str]

class DeepResearchData(BaseModel):
    task_id: Optional[str] = None
    current_span: Optional[Span] = None
    
    # User interaction
    original_query: str = ""
    clarification_questions: List[str] = []
    clarification_answers: List[str] = []
    needs_clarification: bool = True
    
    # Agent outputs
    enriched_instructions: str = ""
    research_report: str = ""
    citations: List[Dict[str, str]] = []
    
    # Conversation history
    agent_messages: List[Dict[str, str]] = []

class DeepResearchStateMachine(StateMachine[DeepResearchData]):
    @override
    async def terminal_condition(self) -> bool:
        return self.get_current_state() == DeepResearchState.COMPLETED