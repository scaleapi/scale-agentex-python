from typing import Optional, override
from agentex.lib.sdk.state_machine.state_machine import StateMachine

from agentex.lib import adk
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.lib.types.llm_messages import LLMConfig, SystemMessage, UserMessage
from agentex.lib.utils.logging import make_logger

from state_machines.deep_research import DeepResearchData, DeepResearchState

logger = make_logger(__name__)


FOLLOW_UP_QUESTION_TEMPLATE = """
Given the following research query from the user, ask a follow up question to clarify the research direction.
<query>
{{ user_query }}
</query>

{% if follow_up_questions|length > 0 %}
The following are follow up questions and answers that have been asked/given so far:
{% for q in follow_up_questions %}
Q: {{ follow_up_questions[loop.index0] }}
A: {{ follow_up_responses[loop.index0] }}
{% endfor %}
{% endif %}

Return the follow up question and nothing else.
Follow up question: 
"""

class ClarifyUserQueryWorkflow(StateWorkflow):
    """Workflow for engaging in follow-up questions."""

    @override
    async def execute(self, state_machine: StateMachine, state_machine_data: Optional[DeepResearchData] = None) -> str:
        """Execute the workflow."""
        if state_machine_data is None:
            return DeepResearchState.PERFORMING_DEEP_RESEARCH
            
        if state_machine_data.n_follow_up_questions_to_ask == 0:
            # No more follow-up questions to ask, proceed to deep research
            return DeepResearchState.PERFORMING_DEEP_RESEARCH
        
        # Generate follow-up question prompt
        if state_machine_data.task_id and state_machine_data.current_span:
            follow_up_question_generation_prompt = await adk.utils.templating.render_jinja(
                trace_id=state_machine_data.task_id,
                template=FOLLOW_UP_QUESTION_TEMPLATE,
                variables={
                    "user_query": state_machine_data.user_query,
                    "follow_up_questions": state_machine_data.follow_up_questions,
                    "follow_up_responses": state_machine_data.follow_up_responses
                },
                parent_span_id=state_machine_data.current_span.id,
            )
            
            task_message = await adk.providers.litellm.chat_completion_stream_auto_send(
                task_id=state_machine_data.task_id,
                llm_config=LLMConfig(
                    model="gpt-4o-mini",
                    messages=[
                        SystemMessage(content="You are assistant that follows exact instructions without outputting any other text except your response to the user's exact request."),
                        UserMessage(content=follow_up_question_generation_prompt),
                    ],
                    stream=True,
                ),
                trace_id=state_machine_data.task_id,
                parent_span_id=state_machine_data.current_span.id,
            )
            follow_up_question = task_message.content.content

            # Update with follow-up question
            state_machine_data.follow_up_questions.append(follow_up_question)

            # Decrement the number of follow-up questions to ask
            state_machine_data.n_follow_up_questions_to_ask -= 1

            logger.info(f"Current research data: {state_machine_data}")

            # Always go back to waiting for user input to get their response
            return DeepResearchState.WAITING_FOR_USER_INPUT
        else:
            return DeepResearchState.PERFORMING_DEEP_RESEARCH 