import os
from datetime import timedelta
from typing import override
from temporalio import workflow
from temporalio.common import RetryPolicy
from agentex.lib import adk
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from mcp import StdioServerParameters
from state_machines.deep_research import DeepResearchState
from deep_research_prompts import RESEARCH_AGENT_INSTRUCTIONS, RESEARCH_MODEL
from activities.deep_research_activities import DeepResearchParams

logger = make_logger(__name__)

MCP_SERVERS = [
    StdioServerParameters(
        command="uvx",
        args=["openai-websearch-mcp"],
        env={"OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")}
    ),
    # Custom file search MCP server (see Phase 5)
]

class ResearchWorkflow(StateWorkflow):
    @override
    async def execute(self, state_machine, state_machine_data=None):
        logger.info("ResearchWorkflow: Starting execution")
        logger.info(f"ResearchWorkflow: state_machine_data type: {type(state_machine_data)}")
        logger.info(f"ResearchWorkflow: state_machine_data is None: {state_machine_data is None}")
        
        if state_machine_data:
            logger.info(f"ResearchWorkflow: enriched_instructions exists: {hasattr(state_machine_data, 'enriched_instructions')}")
            logger.info(f"ResearchWorkflow: enriched_instructions value: '{state_machine_data.enriched_instructions if hasattr(state_machine_data, 'enriched_instructions') else 'N/A'}'")
            logger.info(f"ResearchWorkflow: enriched_instructions length: {len(state_machine_data.enriched_instructions) if hasattr(state_machine_data, 'enriched_instructions') else 0}")
            logger.info(f"ResearchWorkflow: clarification_questions: {len(state_machine_data.clarification_questions) if hasattr(state_machine_data, 'clarification_questions') else 0}")
            logger.info(f"ResearchWorkflow: clarification_answers: {len(state_machine_data.clarification_answers) if hasattr(state_machine_data, 'clarification_answers') else 0}")
        
        # Ensure we have the necessary data
        if not state_machine_data or not state_machine_data.enriched_instructions:
            logger.error("ResearchWorkflow: Missing enriched instructions, returning to waiting")
            logger.error(f"ResearchWorkflow: Failure reason - state_machine_data: {state_machine_data is not None}, enriched_instructions: {state_machine_data.enriched_instructions if state_machine_data else 'N/A'}")
            return DeepResearchState.WAITING_FOR_INPUT
            
        logger.info(f"ResearchWorkflow: Starting research with instructions: {state_machine_data.enriched_instructions[:200]}...")
        
        # Notify user
        if state_machine_data.task_id:
            await adk.messages.create(
                task_id=state_machine_data.task_id,
                content=TextContent(
                    author="agent",
                    content="Starting deep research based on your requirements..."
                )
            )
        
        # Run deep research using activity to avoid workflow restrictions
        logger.info("ResearchWorkflow: Calling deep research activity")
        
        if not state_machine_data.task_id:
            logger.error("ResearchWorkflow: Missing task_id")
            return DeepResearchState.WAITING_FOR_INPUT
        
        # Prepare parameters for the activity
        research_params = DeepResearchParams(
            task_id=state_machine_data.task_id,
            enriched_instructions=state_machine_data.enriched_instructions,
            research_model=RESEARCH_MODEL,
            research_instructions=RESEARCH_AGENT_INSTRUCTIONS,
            trace_id=state_machine_data.task_id,
            parent_span_id=state_machine_data.current_span.id if state_machine_data.current_span else None
        )
        
        # Execute the deep research activity
        logger.info("ResearchWorkflow: Executing deep research activity")
        try:
            result = await workflow.execute_activity(
                "run_deep_research",
                research_params,
                start_to_close_timeout=timedelta(hours=2),  # 2 hours timeout for complex research
                heartbeat_timeout=timedelta(minutes=5),  # 5 minute heartbeat
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=30),
                    maximum_interval=timedelta(minutes=5)
                )
            )
            
            logger.info("ResearchWorkflow: Deep research activity completed")
            # Activity results are serialized to dicts by Temporal
            state_machine_data.research_report = result["research_report"]
            state_machine_data.citations = result["citations"]
            
            logger.info(f"ResearchWorkflow: Research completed, report length: {len(result['research_report'])} chars")
            logger.info("ResearchWorkflow: Transitioning to WAITING_FOR_INPUT state")
            return DeepResearchState.WAITING_FOR_INPUT
            
        except Exception as e:
            logger.error(f"ResearchWorkflow: Failed to execute deep research activity: {e}")
            logger.error(f"ResearchWorkflow: Error type: {type(e).__name__}")
            
            # Send error message to user
            await adk.messages.create(
                task_id=state_machine_data.task_id,
                content=TextContent(
                    author="agent",
                    content=f"I encountered an error while conducting the research: {str(e)}. Please try again or rephrase your request."
                )
            )
            
            # Return to waiting state so user can try again
            logger.info("ResearchWorkflow: Returning to WAITING_FOR_INPUT state after error")
            return DeepResearchState.WAITING_FOR_INPUT