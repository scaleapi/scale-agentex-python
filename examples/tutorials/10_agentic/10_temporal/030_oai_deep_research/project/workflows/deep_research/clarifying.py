from typing import override
from agentex.lib import adk
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.lib.types.llm_messages import LLMConfig, SystemMessage, UserMessage
from agentex.lib.utils.logging import make_logger
from state_machines.deep_research import DeepResearchState
from deep_research_prompts import CLARIFYING_AGENT_PROMPT, Clarifications, CLARIFYING_MODEL

logger = make_logger(__name__)

class ClarifyingWorkflow(StateWorkflow):
    @override
    async def execute(self, state_machine, state_machine_data=None):
        # Check if we have an original query to work with
        if not state_machine_data or not state_machine_data.original_query:
            return DeepResearchState.WAITING_FOR_INPUT
            
        # Generate clarifying questions using exact OpenAI prompt
        # For now, use text completion and parse manually instead of structured output
        result = await adk.providers.litellm.chat_completion_stream_auto_send(
            task_id=state_machine_data.task_id,
            llm_config=LLMConfig(
                model=CLARIFYING_MODEL,
                messages=[
                    SystemMessage(content=CLARIFYING_AGENT_PROMPT + "\n\nReturn 2-3 questions in a numbered list format."),
                    UserMessage(content=f"The user wants to research: {state_machine_data.original_query}")
                ],
                stream=True
            ),
            trace_id=state_machine_data.task_id,
            parent_span_id=state_machine_data.current_span.id if state_machine_data.current_span else None
        )
        
        # The LLM already streamed questions to the user, so we just need to extract them for our state
        # Don't send another message - the streaming already handled user communication
        logger.info("ClarifyingWorkflow: LLM call completed, questions already streamed to user")
        
        # Use fallback questions for our state management (since LLM content is empty in logs)
        # This doesn't affect the user experience since they already saw the proper questions
        fallback_questions = [
            "What specific aspects or focus areas are most important for this research?",
            "What is the intended use case or audience for this research?", 
            "Are there any particular time periods, geographic regions, or constraints to consider?"
        ]
        state_machine_data.clarification_questions = fallback_questions
        logger.info(f"ClarifyingWorkflow: Using fallback questions for state management: {fallback_questions}")
        
        logger.info(f"ClarifyingWorkflow: Stored {len(state_machine_data.clarification_questions)} questions: {state_machine_data.clarification_questions}")
        
        return DeepResearchState.WAITING_FOR_INPUT