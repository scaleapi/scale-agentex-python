"""Claude Agents SDK MVP - Minimal working example

This workflow demonstrates the basic integration pattern between Claude Agents SDK
and AgentEx's Temporal architecture.

What this proves:
- ✅ Claude agent runs in Temporal workflow
- ✅ File operations isolated to workspace
- ✅ Basic text streaming to UI
- ✅ Visible in Temporal UI as activities
- ✅ Temporal retry policies work

What's missing (see NEXT_STEPS.md):
- Tool call streaming
- Proper plugin architecture
- Subagents
- Tracing
"""
from __future__ import annotations

import os
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from claude_agent_sdk.types import AgentDefinition

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow

# Import Claude activities
from agentex.lib.core.temporal.plugins.claude_agents import (
    run_claude_agent_activity,
    create_workspace_directory,
)

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)


class StateModel(BaseModel):
    """Workflow state for Claude session tracking

    Stores Claude session ID to maintain conversation context across turns.
    This allows Claude to remember previous messages and answer follow-up questions.
    """
    claude_session_id: str | None = None
    turn_number: int = 0


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class ClaudeMvpWorkflow(BaseWorkflow):
    """Minimal Claude agent workflow - MVP v0

    This workflow:
    1. Creates isolated workspace for task
    2. Receives user messages via signals
    3. Runs Claude via Temporal activity
    4. Returns responses to user

    Key features:
    - Durable execution (survives restarts)
    - Workspace isolation
    - Automatic retries
    - Visible in Temporal UI
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._state: StateModel | None = None
        self._task_id = None
        self._trace_id = None
        self._parent_span_id = None
        self._workspace_path = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams):
        """Handle user message - run Claude agent"""

        logger.info(f"Received task message: {params.event.content.content[:100]}...")

        if self._state is None:
            raise ValueError("State is not initialized")

        self._task_id = params.task.id
        self._trace_id = params.task.id
        self._state.turn_number += 1

        # Echo user message to UI
        await adk.messages.create(
            task_id=params.task.id,
            content=params.event.content
        )

        # Wrap in tracing span - THIS IS REQUIRED for ContextInterceptor to work!
        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._state.turn_number}",
            input={
                "prompt": params.event.content.content,
                "session_id": self._state.claude_session_id,
            },
        ) as span:
            self._parent_span_id = span.id if span else None

            try:
                # Define subagents for specialized tasks
                subagents = {
                    'code-reviewer': AgentDefinition(
                        description='Expert code review specialist. Use when analyzing code quality, security, or best practices.',
                        prompt='You are a code review expert. Analyze code for bugs, security issues, and best practices. Be thorough but concise.',
                        tools=['Read', 'Grep', 'Glob'],  # Read-only
                        model='sonnet',
                    ),
                    'file-organizer': AgentDefinition(
                        description='File organization specialist. Use when creating multiple files or organizing project layout.',
                        prompt='You are a file organization expert. Create well-structured projects with clear naming.',
                        tools=['Write', 'Read', 'Bash', 'Glob'],
                        model='haiku',  # Faster model
                    ),
                }

                # Run Claude via activity (manual wrapper for MVP)
                # ContextInterceptor reads _task_id, _trace_id, _parent_span_id and threads to activity!
                result = await workflow.execute_activity(
                run_claude_agent_activity,
                args=[
                    params.event.content.content,  # prompt
                    self._workspace_path,          # workspace
                    ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "Task"],  # allowed tools (Task for subagents!)
                    "acceptEdits",                 # permission mode
                    "You are a helpful coding assistant. Be concise.",  # system prompt
                    self._state.claude_session_id,  # resume session for context!
                    subagents,  # subagent definitions!
                ],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0,
                ),
                )

                # Update session_id for next turn (maintains conversation context)
                new_session_id = result.get("session_id")
                if new_session_id:
                    self._state.claude_session_id = new_session_id
                    logger.info(
                        f"Turn {self._state.turn_number}: "
                        f"session_id={'STARTED' if self._state.turn_number == 1 else 'CONTINUED'} "
                        f"({new_session_id[:16]}...)"
                    )
                else:
                    logger.warning(f"No session_id returned - context may not persist")

                # Response already streamed to UI by activity - no need to send again
                logger.debug(f"Turn {self._state.turn_number} completed successfully")

            except Exception as e:
                logger.error(f"Error running Claude agent: {e}", exc_info=True)
                # Send error message to user
                await adk.messages.create(
                    task_id=params.task.id,
                    content=TextContent(
                        author="agent",
                        content=f"❌ Error: {str(e)}",
                    )
                )
                raise

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams):
        """Initialize workflow - create workspace and send welcome"""

        logger.info(f"Creating Claude MVP workflow for task: {params.task.id}")

        # Initialize state with session tracking
        self._state = StateModel(
            claude_session_id=None,
            turn_number=0,
        )

        # Create workspace via activity (avoids determinism issues with file I/O)
        workspace_root = os.environ.get("CLAUDE_WORKSPACE_ROOT")
        self._workspace_path = await workflow.execute_activity(
            create_workspace_directory,
            args=[params.task.id, workspace_root],
            start_to_close_timeout=timedelta(seconds=10),
        )

        logger.info(f"Workspace ready: {self._workspace_path}")

        # Send welcome message
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    "🚀 **Claude MVP Agent Ready!**\n\n"
                    f"Workspace: `{self._workspace_path}`\n\n"
                    "I'm powered by Claude Agents SDK + Temporal. Try asking me to:\n"
                    "- Create files: *'Create a hello.py file'*\n"
                    "- Read files: *'What's in hello.py?'*\n"
                    "- Run commands: *'List files in the workspace'*\n\n"
                    "Send me a message to get started! 💬"
                ),
                format="markdown",
            )
        )

        # Wait for completion signal
        logger.info("Waiting for task completion...")
        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,  # Long-running workflow
        )

        logger.info("Claude MVP workflow completed")
        return "Task completed successfully"

    @workflow.signal
    async def complete_task_signal(self):
        """Signal to gracefully complete the workflow"""
        logger.info("Received complete_task signal")
        self._complete_task = True
