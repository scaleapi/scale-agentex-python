import typer
from rich import print_json

from agentex import Agentex
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

tasks = typer.Typer()


@tasks.command()
def get(
    task_id: str = typer.Argument(..., help="ID of the task to get"),
):
    """
    Get the task with the given ID.
    """
    logger.info(f"Getting task: {task_id}")
    client = Agentex()
    task = client.tasks.retrieve(task_id=task_id)
    print(f"Full Task {task_id}:")
    print_json(data=task.to_dict())


@tasks.command()
def list():
    """
    List all tasks.
    """
    client = Agentex()
    tasks = client.tasks.list()
    print_json(data=[task.to_dict() for task in tasks])


@tasks.command()
def delete(
    task_id: str = typer.Argument(..., help="ID of the task to delete"),
):
    """
    Delete the task with the given ID.
    """
    logger.info(f"Deleting task: {task_id}")
    client = Agentex()
    client.tasks.delete(task_id=task_id)
    logger.info(f"Task deleted: {task_id}")
