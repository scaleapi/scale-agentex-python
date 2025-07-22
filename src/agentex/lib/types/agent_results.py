from typing import Any

from pydantic import BaseModel


class SerializableRunResult(BaseModel):
    """
    Serializable version of RunResult.

    Attributes:
        final_output: The final output of the run.
        final_input_list: The final input list of the run.
    """

    final_output: Any
    final_input_list: list[dict[str, Any]]


class SerializableRunResultStreaming(BaseModel):
    """
    Serializable version of RunResultStreaming.

    Attributes:
        final_output: The final output of the run.
        final_input_list: The final input list of the run.
    """

    final_output: Any
    final_input_list: list[dict[str, Any]]
