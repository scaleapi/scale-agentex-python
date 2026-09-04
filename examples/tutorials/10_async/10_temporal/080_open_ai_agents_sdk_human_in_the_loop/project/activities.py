import random
import asyncio

from temporalio import activity, workflow
from temporalio.workflow import ParentClosePolicy

from project.child_workflow import ChildWorkflow
from agentex.lib.environment_variables import EnvironmentVariables

environment_variables = EnvironmentVariables.refresh()

@activity.defn
async def get_weather(city: str) -> str:
    """Get the weather for a given city"""
    if city == "New York City":
        return "The weather in New York City is 22 degrees Celsius"
    else:
        return "The weather is unknown"

@activity.defn
async def withdraw_money() -> None:
    """Withdraw money from an account"""
    random_number = random.randint(0, 100)
    await asyncio.sleep(random_number)
    print("Withdrew money from account")

@activity.defn
async def deposit_money() -> None:
    """Deposit money into an account"""
    await asyncio.sleep(10)
    print("Deposited money into account")


@activity.defn
async def confirm_order() -> bool:
    """Confirm order"""
    result = await workflow.execute_child_workflow(
    ChildWorkflow.on_task_create,
    environment_variables.WORKFLOW_NAME + "_child",
    id="child-workflow-id",
    parent_close_policy=ParentClosePolicy.TERMINATE,
    )
    
    print(result)
    return True
