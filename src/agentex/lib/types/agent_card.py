from __future__ import annotations

import typing
from typing import Any, get_args, get_origin

from pydantic import BaseModel


class LifecycleState(BaseModel):
    name: str
    description: str = ""
    waits_for_input: bool = False
    accepts: list[str] = []
    transitions: list[str] = []


class AgentLifecycle(BaseModel):
    states: list[LifecycleState]
    initial_state: str
    queries: list[str] = []


class AgentCard(BaseModel):
    protocol: str = "acp"
    lifecycle: AgentLifecycle | None = None
    data_events: list[str] = []
    input_types: list[str] = []
    output_schema: dict | None = None

    @classmethod
    def from_state_machine(
        cls,
        state_machine: Any,
        output_event_model: type[BaseModel] | None = None,
        extra_input_types: list[str] | None = None,
        queries: list[str] | None = None,
    ) -> AgentCard:
        lifecycle_data = state_machine.get_lifecycle()
        lifecycle_data["queries"] = queries or []

        data_events: list[str] = []
        output_schema: dict | None = None
        if output_event_model:
            data_events = extract_literal_values(output_event_model, "type")
            output_schema = output_event_model.model_json_schema()

        derived_input_types: set[str] = set()
        for state in lifecycle_data["states"]:
            derived_input_types.update(state.get("accepts", []))

        return cls(
            lifecycle=AgentLifecycle.model_validate(lifecycle_data),
            data_events=data_events,
            input_types=sorted(derived_input_types | set(extra_input_types or [])),
            output_schema=output_schema,
        )


def extract_literal_values(model: type[BaseModel], field: str) -> list[str]:
    """Extract allowed values from a Literal[...] type annotation on a Pydantic model field."""
    field_info = model.model_fields.get(field)
    if field_info is None:
        return []

    annotation = field_info.annotation
    if annotation is None:
        return []

    # Unwrap Optional (Union[X, None]) to get the inner type
    if get_origin(annotation) is typing.Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        annotation = args[0] if len(args) == 1 else annotation

    if get_origin(annotation) is typing.Literal:
        return list(get_args(annotation))

    return []
