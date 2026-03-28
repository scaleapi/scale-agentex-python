from __future__ import annotations

from enum import Enum
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from agentex.lib.types.agent_card import AgentCard, extract_literal_values
from agentex.lib.sdk.state_machine import State, StateMachine, StateWorkflow
from agentex.lib.utils.model_utils import BaseModel as AgentexBaseModel

# --- Fixtures & helpers ---

class SampleState(str, Enum):
    WAITING = "waiting"
    PROCESSING = "processing"
    DONE = "done"


class WaitingWorkflow(StateWorkflow):
    description = "Waiting for input"
    waits_for_input = True
    accepts = ["text", "doc_upload"]
    transitions = [SampleState.PROCESSING]

    async def execute(self, state_machine, state_machine_data=None):
        return SampleState.PROCESSING


class ProcessingWorkflow(StateWorkflow):
    description = "Processing data"
    accepts = ["text"]
    transitions = [SampleState.DONE, SampleState.WAITING]

    async def execute(self, state_machine, state_machine_data=None):
        return SampleState.DONE


class DoneWorkflow(StateWorkflow):
    description = "Terminal state"
    transitions = []

    async def execute(self, state_machine, state_machine_data=None):
        return SampleState.DONE


class SampleData(AgentexBaseModel):
    pass


class SampleStateMachine(StateMachine[SampleData]):
    async def terminal_condition(self):
        return self.get_current_state() == SampleState.DONE


class SampleOutputEvent(BaseModel):
    type: Literal["plan_update", "status_change", "report_done"]
    data: dict = {}


@pytest.fixture
def sample_states():
    return [
        State(name=SampleState.WAITING, workflow=WaitingWorkflow()),
        State(name=SampleState.PROCESSING, workflow=ProcessingWorkflow()),
        State(name=SampleState.DONE, workflow=DoneWorkflow()),
    ]


@pytest.fixture
def sample_sm(sample_states):
    return SampleStateMachine(initial_state=SampleState.WAITING, states=sample_states)


# --- extract_literal_values ---

class TestExtractLiteralValues:
    def test_literal_field(self):
        class M(BaseModel):
            type: Literal["a", "b", "c"]

        assert extract_literal_values(M, "type") == ["a", "b", "c"]

    def test_optional_literal_field(self):
        """typing.Optional[Literal[...]] should unwrap correctly."""
        class M(BaseModel):
            type: Literal["x", "y"] | None = None

        result = extract_literal_values(M, "type")
        assert result == ["x", "y"]

    def test_non_literal_field(self):
        class M(BaseModel):
            name: str

        assert extract_literal_values(M, "name") == []

    def test_missing_field(self):
        class M(BaseModel):
            name: str

        assert extract_literal_values(M, "nonexistent") == []

    def test_int_literal(self):
        class M(BaseModel):
            code: Literal[1, 2, 3]

        assert extract_literal_values(M, "code") == [1, 2, 3]


# --- StateWorkflow defaults ---

class TestStateWorkflowDefaults:
    def test_default_attrs(self):
        assert StateWorkflow.description == ""
        assert StateWorkflow.waits_for_input is False
        assert StateWorkflow.accepts == []
        assert StateWorkflow.transitions == []

    def test_subclass_overrides(self):
        assert WaitingWorkflow.description == "Waiting for input"
        assert WaitingWorkflow.waits_for_input is True
        assert WaitingWorkflow.accepts == ["text", "doc_upload"]
        assert WaitingWorkflow.transitions == [SampleState.PROCESSING]

    def test_subclass_defaults_not_shared(self):
        """Each subclass's list attrs are independent objects."""
        assert WaitingWorkflow.accepts is not ProcessingWorkflow.accepts
        assert WaitingWorkflow.transitions is not ProcessingWorkflow.transitions


# --- StateMachine.get_lifecycle ---

class TestGetLifecycle:
    def test_structure(self, sample_sm):
        lifecycle = sample_sm.get_lifecycle()

        assert "states" in lifecycle
        assert "initial_state" in lifecycle
        assert lifecycle["initial_state"] == "waiting"
        assert len(lifecycle["states"]) == 3

    def test_state_fields(self, sample_sm):
        lifecycle = sample_sm.get_lifecycle()
        states_by_name = {s["name"]: s for s in lifecycle["states"]}

        waiting = states_by_name["waiting"]
        assert waiting["description"] == "Waiting for input"
        assert waiting["waits_for_input"] is True
        assert waiting["accepts"] == ["text", "doc_upload"]
        assert waiting["transitions"] == ["processing"]

        processing = states_by_name["processing"]
        assert processing["description"] == "Processing data"
        assert processing["waits_for_input"] is False
        assert processing["accepts"] == ["text"]
        assert set(processing["transitions"]) == {"done", "waiting"}

    def test_enum_values_resolved(self, sample_sm):
        """Enum state names and transitions should be resolved to .value strings."""
        lifecycle = sample_sm.get_lifecycle()
        for state in lifecycle["states"]:
            assert isinstance(state["name"], str)
            for t in state["transitions"]:
                assert isinstance(t, str)


# --- AgentCard direct construction ---

class TestAgentCardDirect:
    def test_simple_agent(self):
        card = AgentCard(input_types=["text"], data_events=["result"])
        assert card.protocol == "acp"
        assert card.lifecycle is None
        assert card.input_types == ["text"]
        assert card.data_events == ["result"]
        assert card.output_schema is None

    def test_defaults(self):
        card = AgentCard()
        assert card.protocol == "acp"
        assert card.lifecycle is None
        assert card.data_events == []
        assert card.input_types == []
        assert card.output_schema is None

    def test_serialization_roundtrip(self):
        card = AgentCard(input_types=["text"], data_events=["result"])
        dumped = card.model_dump()
        restored = AgentCard.model_validate(dumped)
        assert restored == card


# --- AgentCard.from_state_machine ---

class TestAgentCardFromStateMachine:
    def test_lifecycle_derivation(self, sample_sm):
        card = AgentCard.from_state_machine(state_machine=sample_sm)

        assert card.lifecycle is not None
        assert card.lifecycle.initial_state == "waiting"
        assert len(card.lifecycle.states) == 3

    def test_input_types_union(self, sample_sm):
        """input_types should be the sorted union of all per-state accepts."""
        card = AgentCard.from_state_machine(state_machine=sample_sm)
        assert card.input_types == ["doc_upload", "text"]

    def test_extra_input_types(self, sample_sm):
        card = AgentCard.from_state_machine(
            state_machine=sample_sm,
            extra_input_types=["admin_command"],
        )
        assert "admin_command" in card.input_types
        assert card.input_types == ["admin_command", "doc_upload", "text"]

    def test_data_events_extraction(self, sample_sm):
        card = AgentCard.from_state_machine(
            state_machine=sample_sm,
            output_event_model=SampleOutputEvent,
        )
        assert card.data_events == ["plan_update", "status_change", "report_done"]

    def test_output_schema_generation(self, sample_sm):
        card = AgentCard.from_state_machine(
            state_machine=sample_sm,
            output_event_model=SampleOutputEvent,
        )
        assert card.output_schema is not None
        assert "properties" in card.output_schema
        assert "type" in card.output_schema["properties"]

    def test_queries(self, sample_sm):
        card = AgentCard.from_state_machine(
            state_machine=sample_sm,
            queries=["get_current_state", "get_progress"],
        )
        assert card.lifecycle is not None
        assert card.lifecycle.queries == ["get_current_state", "get_progress"]

    def test_no_output_model(self, sample_sm):
        card = AgentCard.from_state_machine(state_machine=sample_sm)
        assert card.data_events == []
        assert card.output_schema is None


# --- register_agent agent_card merging ---

class TestRegisterAgentCardMerge:
    @pytest.fixture
    def mock_env_vars(self):
        """Minimal EnvironmentVariables mock for register_agent."""
        mock = type("EnvVars", (), {
            "AGENTEX_BASE_URL": "http://localhost:5003",
            "ACP_URL": "http://localhost",
            "ACP_PORT": "8000",
            "AGENT_NAME": "test-agent",
            "AGENT_DESCRIPTION": "Test agent",
            "ACP_TYPE": "sync",
            "AUTH_PRINCIPAL_B64": None,
            "AGENT_ID": None,
            "AGENT_INPUT_TYPE": None,
            "AGENT_API_KEY": None,
        })()
        return mock

    def _make_mock_client(self):
        """Create a mock httpx.AsyncClient that returns a successful registration response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # httpx Response.json() is sync, not async
        mock_response.json.return_value = {
            "id": "agent-123",
            "name": "test-agent",
            "agent_api_key": "key-123",
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    async def test_agent_card_merged_into_metadata(self, mock_env_vars):
        card = AgentCard(input_types=["text"], data_events=["result"])
        mock_client = self._make_mock_client()

        with patch("agentex.lib.utils.registration.get_build_info", return_value={"version": "1.0"}):
            with patch("agentex.lib.utils.registration.httpx.AsyncClient", return_value=mock_client):
                from agentex.lib.utils.registration import register_agent
                await register_agent(mock_env_vars, agent_card=card)

                sent_data = mock_client.post.call_args.kwargs["json"]
                metadata = sent_data["registration_metadata"]

                assert "agent_card" in metadata
                assert metadata["agent_card"]["input_types"] == ["text"]
                assert metadata["agent_card"]["data_events"] == ["result"]
                assert metadata["version"] == "1.0"

    async def test_none_preserved_when_no_card_no_build_info(self, mock_env_vars):
        mock_client = self._make_mock_client()

        with patch("agentex.lib.utils.registration.get_build_info", return_value=None):
            with patch("agentex.lib.utils.registration.httpx.AsyncClient", return_value=mock_client):
                from agentex.lib.utils.registration import register_agent
                await register_agent(mock_env_vars, agent_card=None)

                sent_data = mock_client.post.call_args.kwargs["json"]
                assert sent_data["registration_metadata"] is None

    async def test_card_creates_metadata_when_build_info_none(self, mock_env_vars):
        card = AgentCard(input_types=["text"])
        mock_client = self._make_mock_client()

        with patch("agentex.lib.utils.registration.get_build_info", return_value=None):
            with patch("agentex.lib.utils.registration.httpx.AsyncClient", return_value=mock_client):
                from agentex.lib.utils.registration import register_agent
                await register_agent(mock_env_vars, agent_card=card)

                sent_data = mock_client.post.call_args.kwargs["json"]
                metadata = sent_data["registration_metadata"]
                assert metadata is not None
                assert "agent_card" in metadata
