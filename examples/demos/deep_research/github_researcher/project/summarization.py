"""
Conversation compaction for research agents.

Prevents Temporal payload size limit (~2MB) from being exceeded by compacting
old tool outputs between batch iterations of Runner.run().
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agents import Agent

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Trigger compaction when serialized conversation exceeds this size (bytes).
# Temporal payload limit is ~2MB; we compact well before that.
COMPACTION_BYTE_THRESHOLD = 800_000  # 800 KB

# Always keep the last N tool outputs in full (most recent context for the model).
KEEP_RECENT_OUTPUTS = 3

# Stub text that replaces truncated tool outputs.
TRUNCATED_STUB = "[Previous tool output truncated. Key findings were incorporated into the assistant's analysis.]"


def estimate_payload_size(input_list: List[Dict[str, Any]]) -> int:
    """Estimate the serialized byte size of the conversation."""
    try:
        return len(json.dumps(input_list, default=str))
    except Exception:
        return sum(len(str(item)) for item in input_list)


def should_compact(input_list: List[Dict[str, Any]]) -> bool:
    """Check if the conversation payload exceeds the compaction threshold."""
    size = estimate_payload_size(input_list)
    logger.info("Conversation payload size: %d bytes", size)
    return size > COMPACTION_BYTE_THRESHOLD


def compact_tool_outputs(input_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Replace old tool outputs with short stubs to reduce payload size.

    Keeps the most recent KEEP_RECENT_OUTPUTS tool outputs in full.
    Older outputs are replaced with a truncation stub.

    Works with both Responses API format (function_call_output) and
    Chat Completions format (role=tool).
    """
    # Find indices of tool output items
    output_indices = []
    for i, item in enumerate(input_list):
        if not isinstance(item, dict):
            continue
        # Responses API format
        if item.get("type") == "function_call_output":
            output_indices.append(i)
        # Chat Completions format
        elif item.get("role") == "tool":
            output_indices.append(i)

    if len(output_indices) <= KEEP_RECENT_OUTPUTS:
        logger.info("Only %d tool outputs, no compaction needed", len(output_indices))
        return input_list

    # Truncate all but the most recent N outputs
    indices_to_truncate = output_indices[:-KEEP_RECENT_OUTPUTS]
    compacted = list(input_list)  # shallow copy

    for idx in indices_to_truncate:
        item = compacted[idx]
        # Responses API format
        if item.get("type") == "function_call_output":
            output_val = item.get("output", "")
            if len(str(output_val)) > 200:
                compacted[idx] = {**item, "output": TRUNCATED_STUB}
        # Chat Completions format
        elif item.get("role") == "tool":
            content_val = item.get("content", "")
            if len(str(content_val)) > 200:
                compacted[idx] = {**item, "content": TRUNCATED_STUB}

    before = estimate_payload_size(input_list)
    after = estimate_payload_size(compacted)
    logger.info("Compacted conversation: %d -> %d bytes (%d tool outputs truncated)",
                before, after, len(indices_to_truncate))
    return compacted


def new_summarization_agent() -> Agent:
    """Create a lightweight agent that summarizes research findings."""
    return Agent(
        name="ResearchSummarizer",
        instructions="""Summarize the research conversation concisely. Focus on:
- Key findings and code references discovered
- File paths, function names, and relevant snippets
- What questions were answered and what gaps remain
- Current state of the research

Be comprehensive but concise (3-5 paragraphs). Focus on OUTCOMES, not listing every tool call.""",
        model="gpt-4.1-mini",
        tools=[],
    )


def find_last_summary_index(input_list: List[Dict[str, Any]]) -> Optional[int]:
    """Find the index of the last summary message."""
    for i in range(len(input_list) - 1, -1, -1):
        item = input_list[i]
        if isinstance(item, dict) and item.get("_summary") is True:
            return i
    return None


def apply_summary_to_input_list(
    input_list: List[Dict[str, Any]],
    summary_text: str,
    original_query: str,
) -> List[Dict[str, Any]]:
    """Replace the conversation with a summary + resume instruction."""
    return [
        {"role": "user", "content": original_query},
        {"role": "assistant", "content": summary_text, "_summary": True},
        {"role": "user", "content": "Use the above summary of your previous research to continue. If you have enough information, provide your final synthesis. Otherwise, continue searching.", "_synthetic": True},
    ]
