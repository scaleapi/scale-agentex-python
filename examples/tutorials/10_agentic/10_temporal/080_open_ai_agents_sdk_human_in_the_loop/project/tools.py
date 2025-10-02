"""
Human-in-the-Loop Tools for OpenAI Agents SDK + Temporal Integration

Tools that pause agent execution and wait for human input using child workflows and signals.
Pattern: Agent calls tool → spawns child workflow → waits for signal → human approves → continues.
"""

from agents import function_tool
from temporalio import workflow
from temporalio.workflow import ParentClosePolicy

from project.child_workflow import ChildWorkflow
from agentex.lib.environment_variables import EnvironmentVariables

environment_variables = EnvironmentVariables.refresh()

@function_tool
async def wait_for_confirmation() -> str:
    """
    Pause agent execution and wait for human approval via child workflow.
    
    Spawns a child workflow that waits for external signal. Human approves via:
    temporal workflow signal --workflow-id="child-workflow-id" --name="fulfill_order_signal" --input=true
    
    Benefits: Durable waiting, survives system failures, scalable to millions of workflows.
    """
    
    # Spawn child workflow that waits for human signal
    # Child workflow has fixed ID "child-workflow-id" so external systems can signal it
    result = await workflow.execute_child_workflow(
        ChildWorkflow.on_task_create,
        environment_variables.WORKFLOW_NAME + "_child",
        id="child-workflow-id",
        parent_close_policy=ParentClosePolicy.TERMINATE,
    )

    return result