"""Agent for extracting learnings from human interactions."""


from agents import Agent


def new_extract_learnings_agent() -> Agent:
    """
    Create an agent that extracts 1-2 sentence learnings from human interactions.

    This agent analyzes the full conversation context to understand how we got to
    the human interaction and what key insight or decision was made.

    Returns:
        Agent configured to extract a concise learning
    """
    instructions = """
You are a learning extraction agent for a procurement system.

Your job is to analyze only the wait_for_human tool call OUTPUT and extract a concise 1-2 sentence learning that can be applied to future decisions. 
We care about the output as that is what the human actually said. The input is AI generated, we are trying to extract what decision the human made.

For example:

  Example usage from the conversation:
  {
    "arguments": "{\"recommended_action\":\"\"The inspection failed I recommend we re-order the item.\"\"}",
    "call_id": "call_FqWa25mlCKwo8gA3zr4TwHca",
    "name": "wait_for_human",
    "type": "function_call",
    "id": "fc_08a992817d632789006914d90bbb948194bd20eb784f33c2a5",
    "status": "completed"
  }

  Human response received:
  {
    "call_id": "call_FqWa25mlCKwo8gA3zr4TwHca",
    "output": "No, we should not re-order the item. Please remove the item from the master schedule.",
    "type": "function_call_output"
  }
Learning: When we fail inspection, the recommended action is to remove the item from the master schedule.

The rest of the information is just context but the focus should be on understanding what the human wanted to do and why.

Please extract a 1-2 sentence learning from the wait_for_human tool call.
"""

    return Agent(
        name="Extract Learnings Agent",
        instructions=instructions,
        model="gpt-4o",
        tools=[],  # No tools needed - just analysis
    )
