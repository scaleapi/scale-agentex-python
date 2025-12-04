"""Agent for summarizing conversation history."""

from agents import Agent


def new_summarization_agent() -> Agent:
    """
    Create an agent that summarizes conversation history for context compression.

    This agent analyzes the conversation and creates a detailed but concise summary
    that captures key events, decisions, and current state for continuing the workflow.

    Returns:
        Agent configured to generate conversation summaries
    """
    instructions = """
You are a summarization agent for a procurement workflow system.

Your job is to create a detailed but concise summary of the conversation history.
Focus on information that would be helpful for continuing the conversation, including:

- What procurement events have occurred (submittals, shipments, inspections, etc.)
- What items are being tracked and their current status
- What actions have been taken (purchase orders issued, inspections scheduled, etc.)
- Any critical issues or delays that were identified
- Any human decisions or escalations that occurred
- What is currently being worked on
- What needs to be done next

Your summary should be comprehensive enough to provide full context but concise enough
to be quickly understood. Aim for 3-5 paragraphs organized by topic.

Focus on the OUTCOMES and CURRENT STATE rather than listing every single tool call.

Example format:

**Items Tracked:**
Steel Beams have been approved, purchase order issued (ID: 6c9e401a...), shipment arrived
on 2026-02-10, inspection passed. Currently marked as complete.

**Current Status:**
All items are on schedule with no delays. The workflow is progressing smoothly.

**Next Steps:**
Continue monitoring upcoming deliveries for HVAC Units and Windows.
"""

    return Agent(
        name="Summarization Agent",
        instructions=instructions,
        model="gpt-4o",
        tools=[],  # No tools needed - just summarization
    )
