from typing import override
from agentex.lib import adk
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.lib.types.llm_messages import LLMConfig, SystemMessage, UserMessage
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from state_machines.deep_research import DeepResearchState
from deep_research_prompts import TRIAGE_AGENT_INSTRUCTIONS, TRIAGE_MODEL

logger = make_logger(__name__)

class TriageWorkflow(StateWorkflow):
    @override
    async def execute(self, state_machine, state_machine_data=None):
        logger.info("TriageWorkflow: Starting execution")
        
        # Check if we have an original query to work with
        if not state_machine_data or not state_machine_data.original_query:
            logger.warning("TriageWorkflow: No query data, returning to waiting")
            return DeepResearchState.WAITING_FOR_INPUT
            
        # Use LLM to make intelligent triage decision following OpenAI pattern
        triage_prompt = f"""
        Analyze the following user query and decide whether clarifications are required.
        
        User Query: "{state_machine_data.original_query}"
        
        {TRIAGE_AGENT_INSTRUCTIONS}
        
        Respond with either:
        - "CLARIFY" if clarifications are needed
        - "RESEARCH" if the query is clear enough to proceed directly to research
        """
        
        result = await adk.providers.litellm.chat_completion_stream_auto_send(
            task_id=state_machine_data.task_id,
            llm_config=LLMConfig(
                model=TRIAGE_MODEL,
                messages=[
                    SystemMessage(content="You are a triage agent that decides whether user queries need clarification before research."),
                    UserMessage(content=triage_prompt)
                ],
                stream=True
            ),
            trace_id=state_machine_data.task_id,
            parent_span_id=state_machine_data.current_span.id if state_machine_data.current_span else None
        )
        
        logger.info(f"TriageWorkflow: LLM result type: {type(result)}")
        logger.info(f"TriageWorkflow: LLM result: {result}")
        logger.info(f"TriageWorkflow: LLM result.content: {result.content if result else 'No result'}")
        if result and result.content:
            logger.info(f"TriageWorkflow: LLM result.content.content: '{result.content.content}'")
        
        # Parse the triage decision - ensure we have content
        if not result or not result.content or not result.content.content:
            # Default to clarification if we can't parse the response
            decision = "CLARIFY"
            logger.warning("TriageWorkflow: Empty LLM response, defaulting to CLARIFY")
        else:
            decision = result.content.content.strip().upper()
            logger.info(f"TriageWorkflow: LLM decision: '{decision}'")
        
        # More robust decision parsing - handle various response formats
        if "CLARIFY" in decision or "CLARIF" in decision or "YES" in decision or not decision:
            decision = "CLARIFY"
        elif "RESEARCH" in decision or "NO" in decision or "DIRECT" in decision:
            decision = "RESEARCH"
        else:
            # If unclear, default to clarification for better user experience
            logger.warning(f"TriageWorkflow: Unclear decision '{decision}', defaulting to CLARIFY")
            decision = "CLARIFY"
        
        if decision == "CLARIFY":
            state_machine_data.needs_clarification = True
            logger.info("TriageWorkflow: Decision = CLARIFY, transitioning to CLARIFYING state")
            await adk.messages.create(
                task_id=state_machine_data.task_id,
                content=TextContent(
                    author="agent",
                    content="I'll help you with your research. Let me ask a few clarifying questions first to ensure I provide the most relevant and comprehensive research."
                )
            )
            return DeepResearchState.CLARIFYING
        else:  # decision == "RESEARCH"
            state_machine_data.needs_clarification = False
            logger.info("TriageWorkflow: Decision = RESEARCH, transitioning to INSTRUCTION_BUILDING state")
            await adk.messages.create(
                task_id=state_machine_data.task_id,
                content=TextContent(
                    author="agent",
                    content="Your research query is clear. I'll proceed directly to conducting the research."
                )
            )
            return DeepResearchState.INSTRUCTION_BUILDING