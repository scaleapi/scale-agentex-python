"""Utility for extracting new context from human interactions using a "going backwards" approach.

This module prevents re-processing old wait_for_human calls by:
1. Iterating backwards through the conversation
2. Stopping when we hit a previously-processed wait_for_human call
3. Returning only the NEW portion of the conversation
"""

from typing import Any, Set, Dict, List, Tuple, Optional

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


def get_new_wait_for_human_context(
    full_conversation: List[Dict[str, Any]],
    extracted_learning_call_ids: Set[str],
) -> Optional[Tuple[List[Dict[str, Any]], str]]:
    """
    Extract NEW context since the last processed wait_for_human call.

    Similar to OpenCode's filterCompacted() pattern, this function:
    - Iterates backwards through the full conversation history
    - Stops when it finds a wait_for_human call we've already processed
    - Returns only the NEW context

    Args:
        full_conversation: The complete conversation history (self._state.input_list)
        extracted_learning_call_ids: Set of call_ids we've already extracted learnings from

    Returns:
        Tuple of (new_context_messages, call_id) if a new wait_for_human was found, None otherwise
    """
    # Go backwards through the conversation to find new wait_for_human calls
    new_context = []
    found_new_wait_for_human = False
    new_wait_for_human_call_id = None

    for item in reversed(full_conversation):
        # Always collect items as we go backwards
        new_context.append(item)

        # Check if this is a wait_for_human function call
        if isinstance(item, dict) and item.get("type") == "function_call":
            if item.get("name") == "wait_for_human":
                call_id = item.get("call_id")

                # If we've already extracted learning for this call_id, STOP
                if call_id in extracted_learning_call_ids:
                    logger.info(f"Found already-processed wait_for_human call_id: {call_id}, stopping")
                    break

                # This is a NEW wait_for_human call
                if not found_new_wait_for_human:
                    found_new_wait_for_human = True
                    new_wait_for_human_call_id = call_id
                    logger.info(f"Found NEW wait_for_human call_id: {call_id}")

    # If we found a new wait_for_human call, return the new context
    if found_new_wait_for_human:
        # Reverse back to chronological order
        new_context.reverse()
        logger.info(f"Extracted {len(new_context)} messages of new context")
        assert new_wait_for_human_call_id is not None, "call_id should be set when found_new_wait_for_human is True"
        return (new_context, new_wait_for_human_call_id)
    else:
        logger.info("No new wait_for_human calls found")
        return None
