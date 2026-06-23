# ruff: noqa: I001
# Import order matters here to avoid circular imports
# The _modules must be imported before providers/utils

from agentex.lib.adk._modules.acp import ACPModule
from agentex.lib.adk._modules.agents import AgentsModule
from agentex.lib.adk._modules.agent_task_tracker import AgentTaskTrackerModule
from agentex.lib.adk._modules.checkpointer import create_checkpointer
from agentex.lib.adk._modules._langgraph_tracing import create_langgraph_tracing_handler
from agentex.lib.adk._modules._langgraph_async import stream_langgraph_events
from agentex.lib.adk._modules._langgraph_messages import emit_langgraph_messages
from agentex.lib.adk._modules._langgraph_sync import convert_langgraph_to_agentex_events
from agentex.lib.adk._modules._pydantic_ai_async import stream_pydantic_ai_events
from agentex.lib.adk._modules._pydantic_ai_sync import convert_pydantic_ai_to_agentex_events
from agentex.lib.adk._modules._pydantic_ai_tracing import create_pydantic_ai_tracing_handler
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
from agentex.lib.adk._modules.tracing import TracingModule

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
    # Checkpointing / LangGraph
    "create_checkpointer",
    "create_langgraph_tracing_handler",
    "stream_langgraph_events",
    "emit_langgraph_messages",
    "convert_langgraph_to_agentex_events",
    # Pydantic AI
    "stream_pydantic_ai_events",
    "convert_pydantic_ai_to_agentex_events",
    "create_pydantic_ai_tracing_handler",
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
