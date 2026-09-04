"""Smoke tests confirming the auto-send activity param models accept the new
`created_at` field added for workflow-driven monotonic message ordering.

These don't exercise the workflow dispatch path (which requires a Temporal
test environment); they just verify the param surface so callers can rely on
it being available without runtime errors.
"""

from __future__ import annotations

from datetime import datetime, timezone

_TS = datetime(2026, 5, 13, 18, 30, 0, tzinfo=timezone.utc)


def test_chat_completion_stream_auto_send_params_accepts_created_at() -> None:
    from agentex.lib.types.llm_messages import LLMConfig
    from agentex.lib.core.temporal.activities.adk.providers.litellm_activities import (
        ChatCompletionStreamAutoSendParams,
    )

    params = ChatCompletionStreamAutoSendParams(
        task_id="t1",
        llm_config=LLMConfig(model="gpt-4o", messages=[]),
        created_at=_TS,
    )
    assert params.created_at == _TS


def test_chat_completion_auto_send_params_accepts_created_at() -> None:
    from agentex.lib.types.llm_messages import LLMConfig
    from agentex.lib.core.temporal.activities.adk.providers.litellm_activities import (
        ChatCompletionAutoSendParams,
    )

    params = ChatCompletionAutoSendParams(
        task_id="t1",
        llm_config=LLMConfig(model="gpt-4o", messages=[]),
        created_at=_TS,
    )
    assert params.created_at == _TS


def test_run_agent_auto_send_params_accepts_created_at() -> None:
    from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
        RunAgentAutoSendParams,
    )

    params = RunAgentAutoSendParams(
        task_id="t1",
        input_list=[{"role": "user", "content": "hi"}],
        mcp_server_params=[],
        agent_name="x",
        agent_instructions="y",
        created_at=_TS,
    )
    assert params.created_at == _TS


def test_run_agent_streamed_auto_send_params_accepts_created_at() -> None:
    from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
        RunAgentStreamedAutoSendParams,
    )

    params = RunAgentStreamedAutoSendParams(
        task_id="t1",
        input_list=[{"role": "user", "content": "hi"}],
        mcp_server_params=[],
        agent_name="x",
        agent_instructions="y",
        created_at=_TS,
    )
    assert params.created_at == _TS


def test_create_message_params_accepts_created_at() -> None:
    from agentex.types.text_content import TextContent
    from agentex.lib.core.temporal.activities.adk.messages_activities import (
        CreateMessageParams,
    )

    params = CreateMessageParams(
        task_id="t1",
        content=TextContent(author="user", content="hi", format="markdown"),
        created_at=_TS,
    )
    assert params.created_at == _TS


def test_create_messages_batch_params_accepts_created_at() -> None:
    from agentex.types.text_content import TextContent
    from agentex.lib.core.temporal.activities.adk.messages_activities import (
        CreateMessagesBatchParams,
    )

    params = CreateMessagesBatchParams(
        task_id="t1",
        contents=[TextContent(author="user", content="hi", format="markdown")],
        created_at=_TS,
    )
    assert params.created_at == _TS
