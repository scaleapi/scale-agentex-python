from typing import override
from agentex.lib import adk
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.lib.types.llm_messages import LLMConfig, SystemMessage, UserMessage
from agentex.lib.utils.logging import make_logger
from state_machines.deep_research import DeepResearchState
from deep_research_prompts import RESEARCH_INSTRUCTION_AGENT_PROMPT, INSTRUCTION_MODEL

logger = make_logger(__name__)

class InstructionBuilderWorkflow(StateWorkflow):
    @override
    async def execute(self, state_machine, state_machine_data=None):
        logger.info("InstructionBuilderWorkflow: Starting execution")
        
        # Build the user context with Q&A (handle both clarified and direct-to-research flows)
        context_parts = [f"User Query: {state_machine_data.original_query}"]
        
        # Only add Q&A section if there are clarification questions and answers
        if (state_machine_data.clarification_questions and 
            state_machine_data.clarification_answers):
            
            logger.info(f"InstructionBuilderWorkflow: Using clarification Q&A with {len(state_machine_data.clarification_questions)} questions and {len(state_machine_data.clarification_answers)} answers")
            context_parts.extend(["", "Follow-up Q&A:"])
            
            # Handle case where user provides comprehensive answer to all questions at once
            if len(state_machine_data.clarification_answers) == 1 and len(state_machine_data.clarification_questions) > 1:
                # User provided one comprehensive answer to all questions
                context_parts.append("Questions asked:")
                for q in state_machine_data.clarification_questions:
                    context_parts.append(f"- {q}")
                context_parts.append("")
                context_parts.append(f"User's comprehensive response: {state_machine_data.clarification_answers[0]}")
            else:
                # Original logic for matching Q&A pairs
                for q, a in zip(state_machine_data.clarification_questions, state_machine_data.clarification_answers):
                    context_parts.append(f"Q: {q}")
                    context_parts.append(f"A: {a}")
                    context_parts.append("")
        else:
            # Direct-to-research flow: no clarification questions were asked
            logger.info("InstructionBuilderWorkflow: Direct-to-research flow (no clarifications)")
            context_parts.extend(["", "No additional clarifications were needed for this query."])
        
        user_context = "\n".join(context_parts)
        logger.info(f"InstructionBuilderWorkflow: Built context: {user_context[:200]}...")
        
        # Generate enriched instructions using exact OpenAI prompt
        result = await adk.providers.litellm.chat_completion_stream_auto_send(
            task_id=state_machine_data.task_id,
            llm_config=LLMConfig(
                model=INSTRUCTION_MODEL,
                messages=[
                    SystemMessage(content=RESEARCH_INSTRUCTION_AGENT_PROMPT),
                    UserMessage(content=user_context)
                ],
                temperature=0.7,
                stream=True
            ),
            trace_id=state_machine_data.task_id,
            parent_span_id=state_machine_data.current_span.id if state_machine_data.current_span else None
        )
        
        logger.info(f"InstructionBuilderWorkflow: LLM result type: {type(result)}")
        logger.info(f"InstructionBuilderWorkflow: LLM result: {result}")
        logger.info(f"InstructionBuilderWorkflow: LLM result.content: {result.content}")
        logger.info(f"InstructionBuilderWorkflow: LLM result.content.content: {result.content.content if result.content else 'None'}")
        
        # Add null check like triage workflow
        if not result or not result.content or not result.content.content:
            logger.warning("InstructionBuilderWorkflow: Empty LLM response, using fallback instructions")
            # Create a basic instruction as fallback
            state_machine_data.enriched_instructions = f"""
Please conduct comprehensive research on the following query: {state_machine_data.original_query}

Based on the clarification provided:
{user_context}

Provide a detailed report with proper citations and sources.
Format as a comprehensive report with appropriate headers and formatting that ensures clarity and structure.
"""
        else:
            state_machine_data.enriched_instructions = result.content.content
            logger.info(f"InstructionBuilderWorkflow: Generated enriched instructions: {result.content.content[:200]}...")
        
        logger.info(f"InstructionBuilderWorkflow: Final enriched_instructions length: {len(state_machine_data.enriched_instructions)}")
        logger.info("InstructionBuilderWorkflow: Transitioning to RESEARCHING state")
        return DeepResearchState.RESEARCHING