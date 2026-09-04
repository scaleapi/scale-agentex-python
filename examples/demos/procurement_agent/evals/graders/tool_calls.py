"""
Tool call grader - extracts and verifies tool calls from workflow transcripts.
"""
from __future__ import annotations

from typing import Any


def extract_tool_calls(transcript: list[dict[str, Any]]) -> list[str]:
    """
    Extract tool/function names from a workflow transcript.

    The transcript is the messages array from the agent run, containing
    items with type="function_call" for tool invocations.

    Args:
        transcript: List of message dicts from agent execution

    Returns:
        List of tool names that were called
    """
    tool_calls = []
    for item in transcript:
        if isinstance(item, dict):
            # Handle function_call type (from OpenAI agents format)
            if item.get("type") == "function_call":
                tool_name = item.get("name")
                if tool_name:
                    tool_calls.append(tool_name)
            # Handle tool_calls nested in assistant messages
            if item.get("role") == "assistant" and "tool_calls" in item:
                for tc in item.get("tool_calls", []):
                    if isinstance(tc, dict) and "function" in tc:
                        tool_name = tc["function"].get("name")
                        if tool_name:
                            tool_calls.append(tool_name)
    return tool_calls


def assert_required_tools(transcript: list[dict[str, Any]], required: list[str]) -> None:
    """
    Assert that all required tools were called.

    Args:
        transcript: The workflow transcript
        required: List of tool names that must appear

    Raises:
        AssertionError: If any required tool is missing
    """
    called = set(extract_tool_calls(transcript))
    missing = set(required) - called
    if missing:
        raise AssertionError(
            f"Required tools not called: {missing}. "
            f"Tools that were called: {called}"
        )


def assert_forbidden_tools(transcript: list[dict[str, Any]], forbidden: list[str]) -> None:
    """
    Assert that forbidden tools were NOT called.

    This is critical for catching false positives (e.g., flagging conflicts
    when there shouldn't be any).

    Args:
        transcript: The workflow transcript
        forbidden: List of tool names that must NOT appear

    Raises:
        AssertionError: If any forbidden tool was called
    """
    called = set(extract_tool_calls(transcript))
    violations = called & set(forbidden)
    if violations:
        raise AssertionError(
            f"Forbidden tools were called: {violations}. "
            f"These tools should NOT have been invoked in this scenario."
        )
