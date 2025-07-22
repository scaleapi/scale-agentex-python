from enum import Enum
from typing import Dict, List, Optional, override
from agentex.types.span import Span
from pydantic import BaseModel

from agentex.lib.sdk.state_machine import StateMachine


class DeepResearchState(str, Enum):
    """States for the deep research workflow."""
    CLARIFYING_USER_QUERY = "clarifying_user_query"
    PERFORMING_DEEP_RESEARCH = "performing_deep_research"
    WAITING_FOR_USER_INPUT = "waiting_for_user_input"
    COMPLETED = "completed"
    FAILED = "failed"


class DeepResearchData(BaseModel):
    """Data model for the deep research state machine - everything is one continuous research report."""
    task_id: Optional[str] = None
    current_span: Optional[Span] = None
    current_turn: int = 1
    
    # Research report data
    user_query: str = ""
    follow_up_questions: List[str] = []
    follow_up_responses: List[str] = []
    n_follow_up_questions_to_ask: int = 1
    agent_input_list: List[Dict[str, str]] = []
    research_report: str = ""
    research_iteration: int = 0


class DeepResearchStateMachine(StateMachine[DeepResearchData]):
    """State machine for the deep research workflow."""
    
    @override
    async def terminal_condition(self) -> bool:
        """Check if the state machine has reached a terminal state."""
        return self.get_current_state() == DeepResearchState.COMPLETED
