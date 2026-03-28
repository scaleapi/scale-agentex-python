from __future__ import annotations

import types
import typing
from enum import Enum
from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic import BaseModel

if TYPE_CHECKING:
    from agentex.lib.sdk.state_machine.state import State


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
    def from_states(
        cls,
        initial_state: str | Enum,
        states: list[State],
        output_event_model: type[BaseModel] | None = None,
        extra_input_types: list[str] | None = None,
        queries: list[str] | None = None,
    ) -> AgentCard:
        """Build an AgentCard directly from a list[State] + initial_state.

        Agents can share their `states` list between the StateMachine and acp.py
        without constructing a temporary StateMachine instance.
        """
        lifecycle_states = [
            LifecycleState(
                name=state.name,
                description=state.workflow.description,
                waits_for_input=state.workflow.waits_for_input,
                accepts=list(state.workflow.accepts),
                transitions=[
                    t.value if isinstance(t, Enum) else str(t)
                    for t in state.workflow.transitions
                ],
            )
            for state in states
        ]

        initial = initial_state.value if isinstance(initial_state, Enum) else initial_state

        data_events: list[str] = []
        output_schema: dict | None = None
        if output_event_model:
            data_events = extract_literal_values(output_event_model, "type")
            output_schema = output_event_model.model_json_schema()

        derived_input_types: set[str] = set()
        for ls in lifecycle_states:
            derived_input_types.update(ls.accepts)

        return cls(
            lifecycle=AgentLifecycle(
                states=lifecycle_states,
                initial_state=initial,
                queries=queries or [],
            ),
            data_events=data_events,
            input_types=sorted(derived_input_types | set(extra_input_types or [])),
            output_schema=output_schema,
        )

    @classmethod
    def from_state_machine(
        cls,
        state_machine: Any,
        output_event_model: type[BaseModel] | None = None,
        extra_input_types: list[str] | None = None,
        queries: list[str] | None = None,
    ) -> AgentCard:
        """Build an AgentCard from a StateMachine instance. Delegates to from_states()."""
        lifecycle = state_machine.get_lifecycle()
        states_data = lifecycle["states"]
        initial = lifecycle["initial_state"]

        # Reconstruct lightweight State-like objects from the lifecycle dict
        # so we can reuse from_states logic via the dict path
        data_events: list[str] = []
        output_schema: dict | None = None
        if output_event_model:
            data_events = extract_literal_values(output_event_model, "type")
            output_schema = output_event_model.model_json_schema()

        derived_input_types: set[str] = set()
        lifecycle_states = []
        for s in states_data:
            derived_input_types.update(s.get("accepts", []))
            lifecycle_states.append(LifecycleState(
                name=s["name"],
                description=s.get("description", ""),
                waits_for_input=s.get("waits_for_input", False),
                accepts=s.get("accepts", []),
                transitions=s.get("transitions", []),
            ))

        return cls(
            lifecycle=AgentLifecycle(
                states=lifecycle_states,
                initial_state=initial,
                queries=queries or [],
            ),
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

    # Unwrap Optional (Union[X, None] or PEP 604 X | None) to get the inner type
    if get_origin(annotation) is typing.Union or isinstance(annotation, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        annotation = args[0] if len(args) == 1 else annotation

    if get_origin(annotation) is typing.Literal:
        return list(get_args(annotation))

    return []
