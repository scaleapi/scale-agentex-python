# [Temporal] Agent Chat with Guardrails

This tutorial demonstrates how to implement streaming multiturn tool-enabled chat with input and output guardrails using Temporal workflows in AgentEx agents.

## What You'll Learn
- Adding safety guardrails to conversational agents
- Input validation and output filtering
- Implementing content moderation with Temporal
- When to block vs warn vs allow content

## Prerequisites
- Development environment set up (see [main repo README](https://github.com/scaleapi/scale-agentex))
- Backend services running: `make dev` from repository root
- Temporal UI available at http://localhost:8233
- Understanding of agent chat patterns (see [010_agent_chat](../010_agent_chat/))

## Quick Start

```bash
cd examples/tutorials/10_agentic/10_temporal/050_agent_chat_guardrails
uv run agentex agents run --manifest manifest.yaml
```

**Monitor:** Open Temporal UI at http://localhost:8233 to see guardrail checks as workflow activities.

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

## When to Use
- Content moderation and safety requirements
- Compliance with regulatory restrictions
- Brand safety and reputation protection
- Preventing agents from discussing sensitive topics

## Why This Matters
Production agents need safety rails. This pattern shows how to implement content filtering without sacrificing the benefits of Temporal workflows. Guardrail checks become durable activities, visible in Temporal UI for audit and debugging.

**Next:** [060_open_ai_agents_sdk_hello_world](../060_open_ai_agents_sdk_hello_world/) - Integrate OpenAI Agents SDK with Temporal