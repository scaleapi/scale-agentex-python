"""
Summarization utility for managing conversation context.

This module provides functionality to detect when conversation history exceeds
token limits and should be summarized. Follows OpenCode's approach of stopping
at previous summaries to avoid re-summarizing already condensed content.
"""
from typing import Any, Dict, List, Tuple, Optional

import tiktoken

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Configuration constants
SUMMARIZATION_TOKEN_THRESHOLD = 40000  # Trigger summarization at 40k tokens
PRESERVE_LAST_N_TURNS = 10  # Always keep last 10 user turns in full


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text string using tiktoken.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated token count
    """
    try:
        encoding = tiktoken.encoding_for_model("gpt-4o")
        return len(encoding.encode(text))
    except Exception as e:
        # Fallback to rough estimation if tiktoken fails
        logger.warning(f"Token estimation failed, using fallback: {e}")
        return len(text) // 4  # Rough approximation


def should_summarize(input_list: List[Dict[str, Any]]) -> bool:
    """
    Check if the conversation history exceeds the token threshold and needs summarization.

    Args:
        input_list: The conversation history

    Returns:
        True if summarization should be triggered
    """
    total_tokens = 0

    for item in input_list:
        if isinstance(item, dict):
            # Estimate tokens for the entire item (JSON serialized)
            item_str = str(item)
            total_tokens += estimate_tokens(item_str)

    logger.info(f"Total conversation tokens: {total_tokens}")

    if total_tokens > SUMMARIZATION_TOKEN_THRESHOLD:
        logger.info(f"Token threshold exceeded ({total_tokens} > {SUMMARIZATION_TOKEN_THRESHOLD}), summarization needed")
        return True

    return False


def get_messages_to_summarize(
    input_list: List[Dict[str, Any]],
    last_summary_index: Optional[int]
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Get the portion of conversation that should be summarized, following OpenCode's approach.

    Strategy:
    - If there's a previous summary, start from AFTER it (never re-summarize summaries)
    - Find last N user turns and preserve them
    - Return everything in between for summarization

    Args:
        input_list: The full conversation history
        last_summary_index: Index of the last summary message (None if no prior summary)

    Returns:
        Tuple of (messages_to_summarize, start_index, end_index)
        - messages_to_summarize: The slice of conversation to summarize
        - start_index: Where the summarization range starts
        - end_index: Where the summarization range ends (exclusive)
    """
    # Find all user turn indices
    user_turn_indices = []
    for i, item in enumerate(input_list):
        if isinstance(item, dict) and item.get("role") == "user":
            user_turn_indices.append(i)

    # Determine the start index (after last summary, or from beginning)
    if last_summary_index is not None:
        start_index = last_summary_index + 1  # Start AFTER the summary
        logger.info(f"Starting summarization after previous summary at index {last_summary_index}")
    else:
        start_index = 0
        logger.info("No previous summary found, starting from beginning")

    # Determine the end index (preserve last N turns)
    if len(user_turn_indices) >= PRESERVE_LAST_N_TURNS:
        # Find the Nth-from-last user turn
        preserve_from_index = user_turn_indices[-PRESERVE_LAST_N_TURNS]
        end_index = preserve_from_index
        logger.info(f"Preserving last {PRESERVE_LAST_N_TURNS} turns from index {preserve_from_index}")
    else:
        # Not enough turns to preserve, summarize nothing
        end_index = len(input_list)
        logger.warning(f"Only {len(user_turn_indices)} user turns, not enough to summarize (need more than {PRESERVE_LAST_N_TURNS})")

    # Extract the messages to summarize
    if end_index <= start_index:
        logger.info("No messages to summarize (end_index <= start_index)")
        return [], start_index, end_index

    messages_to_summarize = input_list[start_index:end_index]
    logger.info(f"Summarizing {len(messages_to_summarize)} messages from index {start_index} to {end_index}")

    return messages_to_summarize, start_index, end_index


def create_summary_message(summary_text: str) -> Dict[str, Any]:
    """
    Create a summary message in the input_list format.

    Args:
        summary_text: The AI-generated summary text

    Returns:
        A dictionary representing the summary message
    """
    return {
        "role": "assistant",
        "content": summary_text,
        "_summary": True,  # Mark this as a summary message
    }


def create_resume_message() -> Dict[str, Any]:
    """
    Create a resume message that instructs the AI to continue from the summary.

    Returns:
        A dictionary representing the resume instruction
    """
    return {
        "role": "user",
        "content": "Use the above summary to continue from where we left off.",
        "_synthetic": True,  # Mark as system-generated
    }


def apply_summary_to_input_list(
    input_list: List[Dict[str, Any]],
    summary_text: str,
    start_index: int,
    end_index: int
) -> List[Dict[str, Any]]:
    """
    Replace the summarized portion of input_list with the summary message.

    Args:
        input_list: The original conversation history
        summary_text: The AI-generated summary
        start_index: Start of summarized range
        end_index: End of summarized range

    Returns:
        New input_list with summary applied
    """
    # Build new input list: [before summary] + [summary] + [resume] + [after summary]
    before_summary = input_list[:start_index] if start_index > 0 else []
    after_summary = input_list[end_index:]

    summary_msg = create_summary_message(summary_text)
    resume_msg = create_resume_message()

    new_input_list = before_summary + [summary_msg, resume_msg] + after_summary

    logger.info(f"Applied summary: reduced from {len(input_list)} to {len(new_input_list)} messages")

    return new_input_list


def find_last_summary_index(input_list: List[Dict[str, Any]]) -> Optional[int]:
    """
    Find the index of the last summary message in the conversation.

    Args:
        input_list: The conversation history

    Returns:
        Index of the last summary message, or None if no summary exists
    """
    for i in range(len(input_list) - 1, -1, -1):
        item = input_list[i]
        if isinstance(item, dict) and item.get("_summary") is True:
            logger.info(f"Found last summary at index {i}")
            return i

    logger.info("No previous summary found")
    return None
