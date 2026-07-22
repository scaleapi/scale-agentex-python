# ruff: noqa: I001
# Import order matters here to avoid circular imports
# The _modules must be imported before providers/utils

from agentex.lib.adk._modules.acp import ACPModule
from agentex.lib.adk._modules.agents import AgentsModule
from agentex.lib.adk._modules.agent_task_tracker import AgentTaskTrackerModule
from agentex.lib.adk._modules.checkpointer import create_checkpointer
from agentex.lib.adk._modules._langgraph_turn import LangGraphTurn, stream_langgraph_events
from agentex.lib.adk._modules._langgraph_sync import (
    emit_langgraph_messages,
    convert_langgraph_to_agentex_events,
)
from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn, stream_pydantic_ai_events
from agentex.lib.adk._modules._pydantic_ai_sync import convert_pydantic_ai_to_agentex_events
from agentex.lib.adk._modules._openai_sync import convert_openai_to_agentex_events
from agentex.lib.adk._modules._openai_turn import OpenAITurn, openai_usage_to_turn_usage
from agentex.lib.adk._modules._claude_code_sync import convert_claude_code_to_agentex_events
from agentex.lib.adk._modules._claude_code_turn import (
    ClaudeCodeTurn,
    claude_code_usage_to_turn_usage,
)
from agentex.lib.adk._modules._codex_sync import convert_codex_to_agentex_events
from agentex.lib.adk._modules._codex_turn import CodexTurn, codex_usage_to_turn_usage
from agentex.lib.adk._modules.events import EventsModule
from agentex.lib.adk._modules.messages import MessagesModule
from agentex.lib.adk._modules.state import StateModule
from agentex.lib.adk._modules.streaming import StreamingModule
from agentex.lib.adk._modules.tasks import TasksModule
from agentex.lib.adk._modules.tracing import TracingModule, TurnSpan

# Data-source refs for lineage (SGP-6513); implementation lives in core.tracing
from agentex.lib.core.tracing import lineage
from agentex.lib.core.tracing.lineage import DataSourceRef, data_sources

# Unified harness surface (AGX1-375)
from agentex.lib.core.harness import (
    UnifiedEmitter,
    SpanTracer,
    OpenSpan,
    CloseSpan,
    SpanSignal,
    StreamTaskMessage,
    TurnUsage,
    TurnResult,
    HarnessTurn,
)

from agentex.lib.adk import providers
from agentex.lib.adk import utils

acp = ACPModule()
agents = AgentsModule()
tasks = TasksModule()
messages = MessagesModule()
state = StateModule()
streaming = StreamingModule()
tracing = TracingModule()
events = EventsModule()
agent_task_tracker = AgentTaskTrackerModule()

__all__ = [
    # Core
    "acp",
    "agents",
    "tasks",
    "messages",
    "state",
    "streaming",
    "tracing",
    "events",
    "agent_task_tracker",
    "TurnSpan",
    # Lineage data-source refs (SGP-6513)
    "lineage",
    "DataSourceRef",
    "data_sources",
    # Checkpointing / LangGraph
    "create_checkpointer",
    "stream_langgraph_events",
    "emit_langgraph_messages",
    "convert_langgraph_to_agentex_events",
    "LangGraphTurn",
    # Pydantic AI
    "stream_pydantic_ai_events",
    "convert_pydantic_ai_to_agentex_events",
    "PydanticAITurn",
    # OpenAI Agents
    "convert_openai_to_agentex_events",
    "OpenAITurn",
    "openai_usage_to_turn_usage",
    # Claude Code
    "convert_claude_code_to_agentex_events",
    "ClaudeCodeTurn",
    "claude_code_usage_to_turn_usage",
    # Codex
    "convert_codex_to_agentex_events",
    "CodexTurn",
    "codex_usage_to_turn_usage",
    # Unified harness surface (AGX1-375)
    "UnifiedEmitter",
    "SpanTracer",
    "OpenSpan",
    "CloseSpan",
    "SpanSignal",
    "StreamTaskMessage",
    "TurnUsage",
    "TurnResult",
    "HarnessTurn",
    # Providers
    "providers",
    # Utils
    "utils",
]
