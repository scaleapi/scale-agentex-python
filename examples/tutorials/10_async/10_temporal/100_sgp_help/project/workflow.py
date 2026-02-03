"""SGP Help Agent - Workflow for answering questions about Scale Generative Platform.

This workflow demonstrates:
- Multi-repo setup with git cloning
- Read-only Claude agent with citation-focused system prompt
- MCP server integration for SGP docs
- Session continuity for multi-turn conversations
"""
from __future__ import annotations

import os
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

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

# Import custom git operations activity
from project.activities import setup_sgp_repos

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)


class StateModel(BaseModel):
    """Workflow state for SGP Help session tracking.

    Tracks:
    - Claude session ID for conversation continuity
    - Turn number for logging
    - Repo setup status and path
    """
    claude_session_id: str | None = None
    turn_number: int = 0
    repos_ready: bool = False
    repos_path: str | None = None


@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class SGPHelpWorkflow(BaseWorkflow):
    """SGP Help Agent workflow.

    This workflow:
    1. Creates isolated workspace for task
    2. Clones SGP repos (scaleapi, sgp, sgp-solutions) with caching
    3. Receives user questions via signals
    4. Runs Claude with read-only tools and SGP docs MCP server
    5. Returns answers with GitHub URL citations

    Key features:
    - Multi-repo workspace setup
    - Read-only operation (no code editing)
    - Citation-focused responses
    - MCP integration for docs
    - Session continuity across turns
    """

    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False
        self._state: StateModel | None = None
        self._task_id = None
        self._trace_id = None
        self._parent_span_id = None
        self._workspace_path = None
        self._repos_path = None

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams):
        """Handle user question - run Claude agent with SGP context."""

        logger.info(f"Received question: {params.event.content.content[:100]}...")

        if self._state is None:
            raise ValueError("State is not initialized")

        if not self._state.repos_ready:
            raise ValueError("Repos not ready - initialization may have failed")

        self._task_id = params.task.id
        self._trace_id = params.task.id
        self._state.turn_number += 1

        # Echo user message to UI
        await adk.messages.create(
            task_id=params.task.id,
            content=params.event.content
        )

        # Wrap in tracing span
        async with adk.tracing.span(
            trace_id=params.task.id,
            name=f"Turn {self._state.turn_number}",
            input={
                "prompt": params.event.content.content,
                "session_id": self._state.claude_session_id,
                "repos_path": self._repos_path,
            },
        ) as span:
            self._parent_span_id = span.id if span else None

            try:
                # SGP-focused system prompt with citation guidelines
                system_prompt = """You are an expert on the Scale Generative Platform (SGP).

Your workspace contains 3 repositories:
- **scaleapi/** - Scale API repository
  - Focus searches on: packages/egp-api-backend/ (SGP API backend)
  - Focus searches on: packages/egp-annotation/ (SGP annotation system)
- **sgp/** - SGP core platform
- **sgp-solutions/** - Example implementations and solutions

Guidelines for answering questions:

1. **Always cite sources with GitHub URLs:**
   - Format: https://github.com/scaleapi/{repo}/blob/main/{path}#L{start_line}-L{end_line}
   - Example: "The authentication handler is in `scaleapi/packages/egp-api-backend/auth.py`"
     https://github.com/scaleapi/scaleapi/blob/main/packages/egp-api-backend/auth.py#L42-L56

2. **Read-only mode:**
   - Use Read, Grep, Glob, and Bash (for git log/diff/blame only)
   - You cannot edit code - you're here to answer questions

3. **Multi-repo awareness:**
   - Search all 3 repos for complete answers
   - For scaleapi repo, focus on packages/egp-api-backend/ and packages/egp-annotation/
   - Mention which repo contains the answer

4. **Repo-specific guidance:**
   - scaleapi/packages/egp-api-backend/ - API implementation, endpoints, business logic
   - scaleapi/packages/egp-annotation/ - Annotation features and UI
   - sgp/ - Core platform code, shared libraries
   - sgp-solutions/ - Working examples, tutorials, sample implementations

5. **Use documentation:**
   - Check SGP docs via the sgp-docs tool when available
   - Combine code references with doc links

Example answer format:
> The SGP API authentication uses JWT tokens. The main authentication handler is in:
> `scaleapi/packages/egp-api-backend/src/auth/jwt_handler.py`
>
> See: https://github.com/scaleapi/scaleapi/blob/main/packages/egp-api-backend/src/auth/jwt_handler.py#L15-L42
>
> For more details, see the authentication docs: [link from sgp-docs tool]
"""

                # Read-only tools only
                allowed_tools = ["Read", "Grep", "Glob", "Bash"]

                # MCP server configuration for SGP docs
                # Note: The exact transport format depends on Claude Agent SDK support
                mcp_servers = {
                    "sgp-docs": {
                        "url": "https://docs.gp.scale.com/mcp",
                        "transport": "sse"
                    }
                }

                # Run Claude via activity
                result = await workflow.execute_activity(
                    run_claude_agent_activity,
                    args=[
                        params.event.content.content,  # prompt
                        self._repos_path,              # cwd = repos directory
                        allowed_tools,                 # read-only tools
                        "bypassPermissions",           # no editing needed
                        system_prompt,                 # SGP expert prompt
                        self._state.claude_session_id, # resume session
                        None,                          # no subagents
                        mcp_servers,                   # SGP docs MCP server
                    ],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        maximum_attempts=3,
                        initial_interval=timedelta(seconds=1),
                        maximum_interval=timedelta(seconds=10),
                        backoff_coefficient=2.0,
                    ),
                )

                # Update session_id for next turn
                new_session_id = result.get("session_id")
                if new_session_id:
                    self._state.claude_session_id = new_session_id
                    logger.info(
                        f"Turn {self._state.turn_number}: "
                        f"session_id={'STARTED' if self._state.turn_number == 1 else 'CONTINUED'} "
                        f"({new_session_id[:16]}...)"
                    )
                else:
                    logger.warning("No session_id returned - context may not persist")

                logger.debug(f"Turn {self._state.turn_number} completed successfully")

            except Exception as e:
                logger.error(f"Error running SGP help agent: {e}", exc_info=True)
                await adk.messages.create(
                    task_id=params.task.id,
                    content=TextContent(
                        author="agent",
                        content=f"Error: {str(e)}",
                    )
                )
                raise

    @workflow.run
    async def on_task_create(self, params: CreateTaskParams):
        """Initialize workflow - create workspace and setup SGP repos."""

        logger.info(f"Creating SGP Help workflow for task: {params.task.id}")

        # Initialize state
        self._state = StateModel(
            claude_session_id=None,
            turn_number=0,
            repos_ready=False,
            repos_path=None,
        )

        # Create base workspace
        workspace_root = os.environ.get("CLAUDE_WORKSPACE_ROOT")
        self._workspace_path = await workflow.execute_activity(
            create_workspace_directory,
            args=[params.task.id, workspace_root],
            start_to_close_timeout=timedelta(seconds=10),
        )

        logger.info(f"Workspace created: {self._workspace_path}")

        # Setup SGP repos (this may take a few minutes)
        try:
            self._repos_path = await workflow.execute_activity(
                setup_sgp_repos,
                args=[params.task.id, workspace_root],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(seconds=30),
                    backoff_coefficient=2.0,
                ),
            )

            self._state.repos_path = self._repos_path
            self._state.repos_ready = True

            logger.info(f"SGP repos ready: {self._repos_path}")

        except Exception as e:
            logger.error(f"Failed to setup SGP repos: {e}", exc_info=True)
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content=f"Failed to setup SGP repositories: {str(e)}\n\nPlease try again.",
                    format="markdown",
                )
            )
            raise

        # Send welcome message
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=(
                    "**SGP Help Agent Ready**\n\n"
                    f"Workspace: `{self._repos_path}`\n\n"
                    "I can answer questions about the Scale Generative Platform codebase.\n\n"
                    "**Available repositories:**\n"
                    "- `scaleapi/` - Scale API (focus: packages/egp-api-backend/, packages/egp-annotation/)\n"
                    "- `sgp/` - SGP core platform\n"
                    "- `sgp-solutions/` - Example implementations\n\n"
                    "**Example questions:**\n"
                    "- *Where is the SGP API client implemented?*\n"
                    "- *Show me examples from sgp-solutions*\n"
                    "- *How does authentication work in the backend?*\n"
                    "- *What annotation features are available?*\n\n"
                    "I'll provide answers with GitHub URL citations. Ask away!"
                ),
                format="markdown",
            )
        )

        # Wait for completion signal
        logger.info("Waiting for task completion...")
        await workflow.wait_condition(
            lambda: self._complete_task,
            timeout=None,
        )

        logger.info("SGP Help workflow completed")
        return "Task completed successfully"

    @workflow.signal
    async def complete_task_signal(self):
        """Signal to gracefully complete the workflow."""
        logger.info("Received complete_task signal")
        self._complete_task = True
