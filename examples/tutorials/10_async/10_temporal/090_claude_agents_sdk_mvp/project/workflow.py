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

import os
from pathlib import Path
from temporalio import workflow
from temporalio import activity
from datetime import timedelta

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.types.text_content import TextContent
from agentex.lib.utils.logging import make_logger

# Import Claude activity
from agentex.lib.core.temporal.plugins.claude_agents import run_claude_agent_activity

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)


# Activity for workspace creation (avoids determinism issues)
@activity.defn
async def create_workspace_directory(task_id: str, workspace_root: str | None = None) -> str:
    """Create workspace directory for task - runs as Temporal activity"""
    if workspace_root is None:
        # Use project-relative workspace for local development
        project_dir = Path(__file__).parent.parent
        workspace_root = str(project_dir / "workspace")

    workspace_path = os.path.join(workspace_root, task_id)
    os.makedirs(workspace_path, exist_ok=True)
    logger.info(f"Created workspace: {workspace_path}")
    return workspace_path


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
        self._task_id = None
        self._workspace_path = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams):
        """Handle user message - run Claude agent"""

        logger.info(f"Received task message: {params.event.content.content[:100]}...")

        self._task_id = params.task.id

        # Echo user message to UI
        await adk.messages.create(
            task_id=params.task.id,
            content=params.event.content
        )

        try:
            # Run Claude via activity (manual wrapper for MVP)
            # ContextInterceptor automatically threads task_id to activity!
            result = await workflow.execute_activity(
                run_claude_agent_activity,
                args=[
                    params.event.content.content,  # prompt
                    self._workspace_path,          # workspace
                    ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],  # allowed tools
                    "acceptEdits",                 # permission mode
                    "You are a helpful coding assistant. Be concise.",  # system prompt
                ],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0,
                ),
            )

            logger.info(f"Claude activity completed: {len(result.get('messages', []))} messages")

            # Send Claude's response back to user
            messages = result.get("messages", [])
            if messages:
                # Combine all messages into one response
                combined_content = "\n\n".join(
                    msg.get("content", "") for msg in messages if msg.get("content")
                )

                await adk.messages.create(
                    task_id=params.task.id,
                    content=TextContent(
                        author="agent",
                        content=combined_content or "Claude completed but returned no content.",
                        format="markdown",
                    )
                )
            else:
                await adk.messages.create(
                    task_id=params.task.id,
                    content=TextContent(
                        author="agent",
                        content="⚠️ Claude completed but returned no messages.",
                    )
                )

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

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams):
        """Initialize workflow - create workspace and send welcome"""

        logger.info(f"Creating Claude MVP workflow for task: {params.task.id}")

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
