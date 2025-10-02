"""
OpenAI Agents SDK + Temporal Integration: Hello World Tutorial

This tutorial demonstrates the fundamental integration between OpenAI Agents SDK and Temporal workflows.
It shows how to:

1. Set up a basic Temporal workflow with OpenAI Agents SDK
2. Create a simple agent that responds to user messages
3. See how agent conversations become durable through Temporal
4. Understand the automatic activity creation for model invocations

KEY CONCEPTS DEMONSTRATED:
- Basic agent creation with OpenAI Agents SDK
- Temporal workflow durability for agent conversations
- Automatic activity creation for LLM calls (visible in Temporal UI)
- Long-running agent workflows that can survive restarts

This is the foundation before moving to more advanced patterns with tools and activities.
"""

import json

from agents import Agent, Runner
from temporalio import workflow

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)

@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class ExampleTutorialWorkflow(BaseWorkflow):
    """
    Hello World Temporal Workflow with OpenAI Agents SDK Integration
    
    This workflow demonstrates the basic pattern for integrating OpenAI Agents SDK
    with Temporal workflows. It shows how agent conversations become durable and
    observable through Temporal's workflow engine.
    
    KEY FEATURES:
    - Durable agent conversations that survive process restarts
    - Automatic activity creation for LLM calls (visible in Temporal UI)
    - Long-running workflows that can handle multiple user interactions
    - Full observability and monitoring through Temporal dashboard
    """
    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        """
        Handle incoming user messages and respond using OpenAI Agents SDK
        
        This signal handler demonstrates the basic integration pattern:
        1. Receive user message through Temporal signal
        2. Echo message back to UI for visibility
        3. Create and run OpenAI agent (automatically becomes a Temporal activity)
        4. Return agent's response to user
        
        TEMPORAL INTEGRATION MAGIC:
        - When Runner.run() executes, it automatically creates a "invoke_model_activity" 
        - This activity is visible in Temporal UI with full observability
        - If the LLM call fails, Temporal automatically retries it
        - The entire conversation is durable and survives process restarts
        """
        logger.info(f"Received task message instruction: {params}")
            
        # ============================================================================
        # STEP 1: Echo User Message
        # ============================================================================
        # Echo back the client's message to show it in the UI. This is not done by default
        # so the agent developer has full control over what is shown to the user.
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        # ============================================================================
        # STEP 2: Create OpenAI Agent
        # ============================================================================
        # Create a simple agent using OpenAI Agents SDK. This agent will respond in haikus
        # to demonstrate the basic functionality. No tools needed for this hello world example.
        # 
        # IMPORTANT: The OpenAI Agents SDK plugin (configured in acp.py and run_worker.py)
        # automatically converts agent interactions into Temporal activities for durability.
        
        
        agent = Agent(
            name="Haiku Assistant",
            instructions="You are a friendly assistant who always responds in the form of a haiku. "
                        "Each response should be exactly 3 lines following the 5-7-5 syllable pattern.",
        )

        # ============================================================================
        # STEP 3: Run Agent with Temporal Durability
        # ============================================================================
        # This is where the magic happens! When Runner.run() executes:
        # 1. The OpenAI Agents SDK makes LLM calls to generate responses
        # 2. The plugin automatically wraps these calls as Temporal activities
        # 3. You'll see "invoke_model_activity" appear in the Temporal UI
        # 4. If the LLM call fails, Temporal retries it automatically
        # 5. The conversation state is preserved even if the worker restarts
        
        # IMPORTANT NOTE ABOUT AGENT RUN CALLS:
        # =====================================
        # Notice that we don't need to wrap the Runner.run() call in an activity!
        # This might feel weird for anyone who has used Temporal before, as typically 
        # non-deterministic operations like LLM calls would need to be wrapped in activities.
        # However, the OpenAI Agents SDK plugin is handling all of this automatically 
        # behind the scenes.
        #
        # Another benefit of this approach is that we don't have to serialize the arguments,
        # which would typically be the case with Temporal activities - the plugin handles 
        # all of this for us, making the developer experience much smoother.
        
        # Pass the text content directly to Runner.run (it accepts strings)
        result = await Runner.run(agent, params.event.content.content)

        # ============================================================================
        # STEP 4: Send Response Back to User
        # ============================================================================
        # Send the agent's response back to the user interface
        # The agent's haiku response will be displayed in the chat
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=result.final_output,
            ),
        )

        # ============================================================================
        # WHAT YOU'LL SEE IN TEMPORAL UI:
        # ============================================================================
        # After running this:
        # 1. Go to localhost:8080 (Temporal UI)
        # 2. Find your workflow execution
        # 3. You'll see an "invoke_model_activity" that shows:
        #    - Execution time for the LLM call
        #    - Input parameters (user message)
        #    - Output (agent's haiku response)
        #    - Retry attempts (if any failures occurred)
        #
        # This gives you full observability into your agent's LLM interactions!
        # ============================================================================

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> str:
        """
        Temporal Workflow Entry Point - Long-Running Agent Conversation
        
        This method runs when the workflow starts and keeps the agent conversation alive.
        It demonstrates Temporal's ability to run workflows for extended periods (minutes,
        hours, days, or even years) while maintaining full durability.
        
        TEMPORAL WORKFLOW LIFECYCLE:
        1. Workflow starts when a task is created
        2. Sends initial acknowledgment message to user
        3. Waits indefinitely for user messages (handled by on_task_event_send signal)
        4. Each user message triggers the signal handler which runs the OpenAI agent
        5. Workflow continues running until explicitly completed or canceled
        
        DURABILITY BENEFITS:
        - Workflow survives worker restarts, deployments, infrastructure failures
        - All agent conversation history is preserved in Temporal's event store
        - Can resume from exact point of failure without losing context
        - Scales to handle millions of concurrent agent conversations
        """
        logger.info(f"Received task create params: {params}")

        # ============================================================================
        # WORKFLOW INITIALIZATION: Send Welcome Message
        # ============================================================================
        # Acknowledge that the task has been created and the agent is ready.
        # This message appears once when the conversation starts.
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"🌸 Hello! I'm your Haiku Assistant, powered by OpenAI Agents SDK + Temporal! 🌸\n\n"
                       f"I'll respond to all your messages in beautiful haiku form. "
                       f"This conversation is now durable - even if I restart, our chat continues!\n\n"
                       f"Task created with params:\n{json.dumps(params.params, indent=2)}\n\n"
                       f"Send me a message and I'll respond with a haiku! 🎋",
            ),
        )

        # ============================================================================
        # WORKFLOW PERSISTENCE: Wait for Completion Signal
        # ============================================================================
        # This is the key to Temporal's power: the workflow runs indefinitely,
        # handling user messages through signals (on_task_event_send) until
        # explicitly told to complete.
        #
        # IMPORTANT: This wait_condition keeps the workflow alive and durable:
        # - No timeout = workflow can run forever (perfect for ongoing conversations)
        # - Temporal can handle millions of such concurrent workflows
        # - If worker crashes, workflow resumes exactly where it left off
        # - All conversation state is preserved in Temporal's event log
        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,  # No timeout = truly long-running agent conversation
        )
        return "Agent conversation completed"

    @workflow.signal
    async def complete_task_signal(self) -> None:
        """
        Signal to gracefully complete the agent conversation workflow
        
        This signal can be sent to end the workflow cleanly. In a real application,
        you might trigger this when a user ends the conversation or after a period
        of inactivity.
        """
        logger.info("Received signal to complete the agent conversation")
        self._complete_task = True