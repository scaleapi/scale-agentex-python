# [Agentic] Agent Chat with Guardrails

This tutorial demonstrates how to implement streaming multiturn tool-enabled chat with input and output guardrails using Temporal workflows in AgentEx agents.

## Overview

This example extends the basic agent chat functionality by adding guardrails that can filter both user inputs and AI outputs. This is useful for content moderation, compliance, or preventing certain topics from being discussed.

## Guardrails

### Input Guardrails
- **Spaghetti Guardrail**: Blocks any mention of "spaghetti" in user messages
- **Soup Guardrail**: Blocks any mention of "soup" in user messages

### Output Guardrails  
- **Pizza Guardrail**: Prevents the AI from mentioning "pizza" in responses
- **Sushi Guardrail**: Prevents the AI from mentioning "sushi" in responses

## Testing the Guardrails

To see the guardrails in action:

1. **Test Input Guardrails:**
   - Try: "Tell me about spaghetti" 
   - Try: "What's your favorite soup?"
   - The guardrails will block these messages before they reach the AI

2. **Test Output Guardrails:**
   - Ask: "What are popular Italian foods?" (may trigger pizza guardrail)
   - Ask: "What are popular Japanese foods?" (may trigger sushi guardrail)
   - The AI may generate responses containing these words, but the guardrails will block them

## Implementation Details

The guardrails are implemented as functions that:
- Check the input/output for specific content
- Return a `GuardrailFunctionOutput` with:
  - `tripwire_triggered`: Whether to block the content
  - `output_info`: Metadata about the check
  - `rejection_message`: Custom message shown when content is blocked

See `workflow.py` for the complete implementation.