"""Voice Agent SDK module for building LiveKit-powered voice agents.

This module provides base classes and utilities for creating production-ready
voice agents with state management, guardrails, and streaming support.

Example usage:
    from agentex.voice import VoiceAgentBase, AgentState, AgentResponse
    
    class MyVoiceAgent(VoiceAgentBase):
        def get_system_prompt(self, state, guardrail_override=None):
            return "You are a helpful voice assistant."
        
        def update_state_and_tracing_from_response(self, state, response, span):
            span.output = response
            return state
"""

from agentex.voice.agent import VoiceAgentBase
from agentex.voice.models import AgentState, AgentResponse, ProcessingInfo
from agentex.voice.guardrails import Guardrail, LLMGuardrail

__all__ = [
    "VoiceAgentBase",
    "AgentState",
    "AgentResponse",
    "ProcessingInfo",
    "Guardrail",
    "LLMGuardrail",
]

__version__ = "0.1.0"
