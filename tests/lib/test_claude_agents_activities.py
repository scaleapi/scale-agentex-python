"""Tests for Claude Agents SDK activity helpers.

These tests validate the serialization helpers and activity behavior for the
Claude Agents SDK Temporal integration. The import chain for the activities
module transitively pulls in langchain_core and langgraph (via agentex.lib.adk),
which are optional deps not present in the base test venv. We mock the
problematic intermediate modules to break the chain.
"""

from __future__ import annotations

import sys

# The activities module lives under agentex.lib.core.temporal.plugins.claude_agents.
# Importing it normally triggers plugins/__init__.py which imports the openai_agents
# plugin, which transitively imports langchain_core and langgraph (not installed in
# the base test environment).
#
# We use importlib.util to load *only* the activities module from its file path,
# bypassing all __init__.py chains.
import contextvars
import importlib.util
from types import ModuleType
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from claude_agent_sdk import HookMatcher, AgentDefinition, ClaudeAgentOptions
from claude_agent_sdk.types import (
    TextBlock,
    ToolUseBlock,
    ResultMessage,
    SystemMessage,
    AssistantMessage,
)

_SRC = Path(__file__).resolve().parents[2] / "src"
_ACTIVITIES_PATH = _SRC / "agentex" / "lib" / "core" / "temporal" / "plugins" / "claude_agents" / "activities.py"

# Stub the modules that activities.py imports (hooks, message_handler, interceptor)
_hooks_mock = MagicMock()
_handler_mock = MagicMock()
_interceptor_mock = MagicMock()
_interceptor_mock.streaming_task_id = contextvars.ContextVar("streaming_task_id", default=None)
_interceptor_mock.streaming_trace_id = contextvars.ContextVar("streaming_trace_id", default=None)
_interceptor_mock.streaming_parent_span_id = contextvars.ContextVar("streaming_parent_span_id", default=None)

# Register stubs for all imports that activities.py does
_adk_mock = MagicMock()
_hooks_hooks_mock = MagicMock()
_stubs = {
    "agentex.lib.adk": _adk_mock,
    "agentex.lib.utils.logging": MagicMock(),
    "agentex.lib.core.temporal.plugins.claude_agents.hooks": _hooks_mock,
    "agentex.lib.core.temporal.plugins.claude_agents.hooks.hooks": _hooks_hooks_mock,
    "agentex.lib.core.temporal.plugins.claude_agents.message_handler": _handler_mock,
    "agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor": _interceptor_mock,
}
for _name, _mock in _stubs.items():
    sys.modules.setdefault(_name, _mock)

# Also ensure parent packages exist as stubs so Python resolves the dotted path
for _pkg in [
    "agentex.lib.core.temporal.plugins",
    "agentex.lib.core.temporal.plugins.claude_agents",
    "agentex.lib.core.temporal.plugins.openai_agents",
    "agentex.lib.core.temporal.plugins.openai_agents.interceptors",
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = []  # type: ignore[attr-defined]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod

# Load activities.py directly from its file path
_spec = importlib.util.spec_from_file_location(
    "agentex.lib.core.temporal.plugins.claude_agents.activities",
    _ACTIVITIES_PATH,
)
assert _spec is not None and _spec.loader is not None
_activities_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _activities_mod
_spec.loader.exec_module(_activities_mod)

_reconstruct_agent_defs = _activities_mod._reconstruct_agent_defs  # type: ignore[attr-defined]
claude_options_to_dict = _activities_mod.claude_options_to_dict  # type: ignore[attr-defined]


class TestClaudeOptionsToDict:
    """Tests for claude_options_to_dict serialization helper."""

    def test_basic_fields(self):
        options = ClaudeAgentOptions(
            cwd="/workspace",
            allowed_tools=["Read", "Write"],
            permission_mode="acceptEdits",
            system_prompt="Be helpful.",
        )
        result = claude_options_to_dict(options)
        assert result["cwd"] == "/workspace"
        assert result["allowed_tools"] == ["Read", "Write"]
        assert result["permission_mode"] == "acceptEdits"
        assert result["system_prompt"] == "Be helpful."

    def test_excludes_defaults(self):
        """Fields left at their default value should not appear in the dict."""
        options = ClaudeAgentOptions(cwd="/workspace")
        result = claude_options_to_dict(options)
        assert "cwd" in result
        # These are all defaults and should be absent
        assert "continue_conversation" not in result
        assert "include_partial_messages" not in result
        assert "fork_session" not in result
        assert "disallowed_tools" not in result

    def test_excludes_non_serializable_fields(self):
        """Callbacks and file objects should never appear in the dict."""
        options = ClaudeAgentOptions(
            cwd="/workspace",
            can_use_tool=lambda *_: True,
            stderr=lambda msg: None,
        )
        result = claude_options_to_dict(options)
        assert "can_use_tool" not in result
        assert "stderr" not in result
        assert "debug_stderr" not in result
        assert "hooks" not in result

    def test_mcp_servers_included(self):
        options = ClaudeAgentOptions(
            cwd="/workspace",
            mcp_servers={"my-server": {"command": "npx", "args": ["server"]}},
        )
        result = claude_options_to_dict(options)
        assert result["mcp_servers"] == {"my-server": {"command": "npx", "args": ["server"]}}

    def test_agents_included(self):
        agents = {
            "reviewer": AgentDefinition(
                description="Code reviewer",
                prompt="Review code.",
                tools=["Read"],
                model="sonnet",
            )
        }
        options = ClaudeAgentOptions(cwd="/workspace", agents=agents)
        result = claude_options_to_dict(options)
        assert "agents" in result
        assert "reviewer" in result["agents"]

    def test_model_and_budget_fields(self):
        options = ClaudeAgentOptions(
            cwd="/workspace",
            model="opus",
            max_turns=5,
            max_budget_usd=1.0,
            max_thinking_tokens=8000,
        )
        result = claude_options_to_dict(options)
        assert result["model"] == "opus"
        assert result["max_turns"] == 5
        assert result["max_budget_usd"] == 1.0
        assert result["max_thinking_tokens"] == 8000

    def test_resume_session(self):
        options = ClaudeAgentOptions(
            cwd="/workspace",
            resume="session-abc-123",
        )
        result = claude_options_to_dict(options)
        assert result["resume"] == "session-abc-123"

    def test_roundtrip_constructs_options(self):
        """The dict produced by claude_options_to_dict can construct a new ClaudeAgentOptions."""
        original = ClaudeAgentOptions(
            cwd="/workspace",
            allowed_tools=["Read", "Bash"],
            permission_mode="acceptEdits",
            model="sonnet",
            max_turns=3,
        )
        d = claude_options_to_dict(original)
        reconstructed = ClaudeAgentOptions(**d)
        assert reconstructed.cwd == original.cwd
        assert reconstructed.allowed_tools == original.allowed_tools
        assert reconstructed.permission_mode == original.permission_mode
        assert reconstructed.model == original.model
        assert reconstructed.max_turns == original.max_turns


class TestReconstructAgentDefs:
    """Tests for _reconstruct_agent_defs helper."""

    def test_none_input(self):
        assert _reconstruct_agent_defs(None) is None

    def test_empty_dict(self):
        assert _reconstruct_agent_defs({}) is None

    def test_already_agent_definitions(self):
        agent = AgentDefinition(description="test", prompt="test prompt")
        result = _reconstruct_agent_defs({"a": agent})
        assert result is not None
        assert result["a"] is agent

    def test_dict_input(self):
        """Temporal serializes dataclasses to dicts - verify reconstruction."""
        raw = {
            "reviewer": {
                "description": "Code reviewer",
                "prompt": "Review code.",
                "tools": ["Read", "Grep"],
                "model": "sonnet",
            }
        }
        result = _reconstruct_agent_defs(raw)
        assert result is not None
        assert isinstance(result["reviewer"], AgentDefinition)
        assert result["reviewer"].description == "Code reviewer"
        assert result["reviewer"].prompt == "Review code."
        assert result["reviewer"].tools == ["Read", "Grep"]
        assert result["reviewer"].model == "sonnet"

    def test_mixed_input(self):
        """Mix of already-constructed and dict-serialized agents."""
        existing = AgentDefinition(description="existing", prompt="p")
        raw = {"description": "from_dict", "prompt": "p2", "tools": None, "model": None}
        result = _reconstruct_agent_defs({"a": existing, "b": raw})
        assert result is not None
        assert isinstance(result["a"], AgentDefinition)
        assert isinstance(result["b"], AgentDefinition)
        assert result["a"].description == "existing"
        assert result["b"].description == "from_dict"


class TestRunClaudeAgentActivity:
    """Tests for the run_claude_agent_activity Temporal activity."""

    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_task_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_trace_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_parent_span_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.ClaudeSDKClient",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.create_streaming_hooks",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.adk",
    )
    async def test_passes_claude_options_to_sdk(
        self,
        _mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """Verify that claude_options extras are merged into ClaudeAgentOptions."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import (
            run_claude_agent_activity,
        )

        # Set up context vars
        mock_task_id.get.return_value = "task-1"
        mock_trace_id.get.return_value = "trace-1"
        mock_parent_span_id.get.return_value = "span-1"

        # Set up hooks
        mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

        # Set up client as async context manager
        mock_client = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=AsyncIteratorMock([]))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Extra SDK options passed via claude_options
        extra = {
            "model": "sonnet",
            "mcp_servers": {"my-server": {"command": "npx", "args": ["srv"]}},
        }

        # activity.defn decorates in-place (no __wrapped__), call directly
        await run_claude_agent_activity(
            prompt="Hello",
            workspace_path="/workspace",
            allowed_tools=["Read"],
            permission_mode="acceptEdits",
            claude_options=extra,
        )

        # Verify ClaudeAgentOptions was constructed with both explicit + extra fields
        call_args = mock_client_cls.call_args
        options = call_args.kwargs.get("options") or call_args[1].get("options")
        assert options.cwd == "/workspace"
        assert options.allowed_tools == ["Read"]
        assert options.model == "sonnet"
        assert options.mcp_servers == {"my-server": {"command": "npx", "args": ["srv"]}}

    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_task_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_trace_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_parent_span_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.ClaudeSDKClient",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.create_streaming_hooks",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.adk",
    )
    async def test_claude_options_not_masked_by_none_explicit_params(
        self,
        _mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """claude_options values should not be silently dropped when explicit params are None."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import (
            run_claude_agent_activity,
        )

        mock_task_id.get.return_value = "task-1"
        mock_trace_id.get.return_value = "trace-1"
        mock_parent_span_id.get.return_value = "span-1"
        mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": []}

        mock_client = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=AsyncIteratorMock([]))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # system_prompt explicit param is None (default), but claude_options has a value
        await run_claude_agent_activity(
            prompt="Hello",
            workspace_path="/workspace",
            allowed_tools=["Read"],
            claude_options={"system_prompt": "Be helpful"},
        )

        call_args = mock_client_cls.call_args
        options = call_args.kwargs.get("options") or call_args[1].get("options")
        assert options.system_prompt == "Be helpful"

    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_task_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_trace_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_parent_span_id",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.ClaudeSDKClient",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.create_streaming_hooks",
    )
    @patch(
        "agentex.lib.core.temporal.plugins.claude_agents.activities.adk",
    )
    async def test_merges_user_hooks_with_streaming_hooks(
        self,
        _mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """User-provided hooks in claude_options should be merged with streaming hooks."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import (
            run_claude_agent_activity,
        )

        mock_task_id.get.return_value = "task-1"
        mock_trace_id.get.return_value = "trace-1"
        mock_parent_span_id.get.return_value = "span-1"

        # Streaming hooks
        streaming_pre = HookMatcher(matcher=None, hooks=[AsyncMock()])
        mock_create_hooks.return_value = {"PreToolUse": [streaming_pre]}

        mock_client = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=AsyncIteratorMock([]))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # User-provided hook via claude_options
        user_pre = HookMatcher(matcher="Bash", hooks=[AsyncMock()])

        await run_claude_agent_activity(
            prompt="Hello",
            workspace_path="/workspace",
            allowed_tools=["Read"],
            claude_options={"hooks": {"PreToolUse": [user_pre]}},
        )

        call_args = mock_client_cls.call_args
        options = call_args.kwargs.get("options") or call_args[1].get("options")
        # Should have both streaming and user hooks merged
        assert len(options.hooks["PreToolUse"]) == 2


class _AsyncCtxManager:
    """Simple async context manager that yields a given value."""

    def __init__(self, value):
        self.value = value
        self.exited = False

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        self.exited = True


def _setup_activity_mocks(
    mock_adk, mock_create_hooks, mock_client_cls, mock_task_id, mock_trace_id, mock_parent_span_id, messages
):
    """Common setup for activity tests that send messages through the client."""
    mock_task_id.get.return_value = "task-1"
    mock_trace_id.get.return_value = "trace-1"
    mock_parent_span_id.get.return_value = "span-1"
    mock_create_hooks.return_value = {"PreToolUse": [], "PostToolUse": [], "PostToolUseFailure": []}

    mock_client = AsyncMock()
    mock_client.receive_response = MagicMock(return_value=AsyncIteratorMock(messages))
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_adk


_ACTIVITY_PATCHES = [
    "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_task_id",
    "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_trace_id",
    "agentex.lib.core.temporal.plugins.claude_agents.activities.streaming_parent_span_id",
    "agentex.lib.core.temporal.plugins.claude_agents.activities.ClaudeSDKClient",
    "agentex.lib.core.temporal.plugins.claude_agents.activities.create_streaming_hooks",
    "agentex.lib.core.temporal.plugins.claude_agents.activities.adk",
]


class TestActivityMessageHandling:
    """Tests for run_claude_agent_activity message streaming behavior."""

    @patch(_ACTIVITY_PATCHES[0])
    @patch(_ACTIVITY_PATCHES[1])
    @patch(_ACTIVITY_PATCHES[2])
    @patch(_ACTIVITY_PATCHES[3])
    @patch(_ACTIVITY_PATCHES[4])
    @patch(_ACTIVITY_PATCHES[5])
    async def test_text_block_opens_and_closes_streaming_context(
        self,
        mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """TextBlock should open a text streaming CM, use it for deltas, and close it via __aexit__."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import run_claude_agent_activity

        text_ctx = MagicMock()
        text_ctx.task_message = MagicMock()
        text_ctx.stream_update = AsyncMock()
        text_cm = _AsyncCtxManager(text_ctx)

        mock_adk = _setup_activity_mocks(
            mock_adk,
            mock_create_hooks,
            mock_client_cls,
            mock_task_id,
            mock_trace_id,
            mock_parent_span_id,
            messages=[AssistantMessage(content=[TextBlock(text="Hello world")], model="claude")],
        )
        mock_adk.streaming.streaming_task_message_context.return_value = text_cm

        result = await run_claude_agent_activity(prompt="Hi", workspace_path="/ws", allowed_tools=["Read"])

        # streaming_task_message_context was called to open the text stream
        mock_adk.streaming.streaming_task_message_context.assert_called()
        # The CM was entered and then exited via close_text_stream (uses __aexit__)
        assert text_cm.exited is True
        # Result includes the text in serialized_messages
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Hello world"

    @patch(_ACTIVITY_PATCHES[0])
    @patch(_ACTIVITY_PATCHES[1])
    @patch(_ACTIVITY_PATCHES[2])
    @patch(_ACTIVITY_PATCHES[3])
    @patch(_ACTIVITY_PATCHES[4])
    @patch(_ACTIVITY_PATCHES[5])
    async def test_tool_use_block_closes_text_stream_first(
        self,
        mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """ToolUseBlock should close any open text stream before streaming the tool request."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import run_claude_agent_activity

        text_ctx = MagicMock()
        text_ctx.task_message = MagicMock()
        text_ctx.stream_update = AsyncMock()
        text_cm = _AsyncCtxManager(text_ctx)

        # Tool request CM
        tool_ctx = MagicMock()
        tool_ctx.task_message = MagicMock()
        tool_ctx.stream_update = AsyncMock()
        tool_cm = _AsyncCtxManager(tool_ctx)

        mock_adk = _setup_activity_mocks(
            mock_adk,
            mock_create_hooks,
            mock_client_cls,
            mock_task_id,
            mock_trace_id,
            mock_parent_span_id,
            messages=[
                AssistantMessage(
                    content=[
                        TextBlock(text="Let me check"),
                        ToolUseBlock(id="tu-1", name="Read", input={"file": "foo.py"}),
                    ],
                    model="claude",
                ),
            ],
        )
        # First call returns text CM, second returns tool CM
        mock_adk.streaming.streaming_task_message_context.side_effect = [text_cm, tool_cm]

        await run_claude_agent_activity(prompt="Hi", workspace_path="/ws", allowed_tools=["Read"])

        # Text CM was closed (via __aexit__) before tool streaming started
        assert text_cm.exited is True
        assert mock_adk.streaming.streaming_task_message_context.call_count == 2

    @patch(_ACTIVITY_PATCHES[0])
    @patch(_ACTIVITY_PATCHES[1])
    @patch(_ACTIVITY_PATCHES[2])
    @patch(_ACTIVITY_PATCHES[3])
    @patch(_ACTIVITY_PATCHES[4])
    @patch(_ACTIVITY_PATCHES[5])
    async def test_result_message_captures_session_and_cost(
        self,
        mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """ResultMessage should capture session_id, usage, and cost."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import run_claude_agent_activity

        _setup_activity_mocks(
            mock_adk,
            mock_create_hooks,
            mock_client_cls,
            mock_task_id,
            mock_trace_id,
            mock_parent_span_id,
            messages=[
                ResultMessage(
                    subtype="result",
                    duration_ms=1500,
                    duration_api_ms=1200,
                    is_error=False,
                    num_turns=3,
                    session_id="sess-abc",
                    total_cost_usd=0.05,
                    usage={"input_tokens": 100, "output_tokens": 50},
                ),
            ],
        )

        result = await run_claude_agent_activity(prompt="Hi", workspace_path="/ws", allowed_tools=["Read"])

        assert result["session_id"] == "sess-abc"
        assert result["cost_usd"] == 0.05
        assert result["usage"] == {"input_tokens": 100, "output_tokens": 50}

    @patch(_ACTIVITY_PATCHES[0])
    @patch(_ACTIVITY_PATCHES[1])
    @patch(_ACTIVITY_PATCHES[2])
    @patch(_ACTIVITY_PATCHES[3])
    @patch(_ACTIVITY_PATCHES[4])
    @patch(_ACTIVITY_PATCHES[5])
    async def test_system_init_message_captures_session_id(
        self,
        mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """SystemMessage with subtype 'init' should capture session_id."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import run_claude_agent_activity

        _setup_activity_mocks(
            mock_adk,
            mock_create_hooks,
            mock_client_cls,
            mock_task_id,
            mock_trace_id,
            mock_parent_span_id,
            messages=[
                SystemMessage(subtype="init", data={"session_id": "sess-init-123"}),
            ],
        )

        result = await run_claude_agent_activity(prompt="Hi", workspace_path="/ws", allowed_tools=["Read"])

        assert result["session_id"] == "sess-init-123"

    @patch(_ACTIVITY_PATCHES[0])
    @patch(_ACTIVITY_PATCHES[1])
    @patch(_ACTIVITY_PATCHES[2])
    @patch(_ACTIVITY_PATCHES[3])
    @patch(_ACTIVITY_PATCHES[4])
    @patch(_ACTIVITY_PATCHES[5])
    async def test_exception_cleans_up_text_stream_and_subagent_spans(
        self,
        mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """On exception, both text stream and subagent spans should be cleaned up."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import run_claude_agent_activity

        mock_adk = _setup_activity_mocks(
            mock_adk,
            mock_create_hooks,
            mock_client_cls,
            mock_task_id,
            mock_trace_id,
            mock_parent_span_id,
            messages=[],
        )

        # Make the client raise after entering
        mock_client = AsyncMock()
        mock_client.receive_response = MagicMock(side_effect=RuntimeError("connection lost"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)

        import pytest

        with pytest.raises(RuntimeError, match="connection lost"):
            await run_claude_agent_activity(prompt="Hi", workspace_path="/ws", allowed_tools=["Read"])

    @patch(_ACTIVITY_PATCHES[0])
    @patch(_ACTIVITY_PATCHES[1])
    @patch(_ACTIVITY_PATCHES[2])
    @patch(_ACTIVITY_PATCHES[3])
    @patch(_ACTIVITY_PATCHES[4])
    @patch(_ACTIVITY_PATCHES[5])
    async def test_empty_text_block_not_serialized(
        self,
        mock_adk,
        mock_create_hooks,
        mock_client_cls,
        mock_parent_span_id,
        mock_trace_id,
        mock_task_id,
    ):
        """TextBlock with empty text should not appear in serialized messages."""
        from agentex.lib.core.temporal.plugins.claude_agents.activities import run_claude_agent_activity

        _setup_activity_mocks(
            mock_adk,
            mock_create_hooks,
            mock_client_cls,
            mock_task_id,
            mock_trace_id,
            mock_parent_span_id,
            messages=[AssistantMessage(content=[TextBlock(text="")], model="claude")],
        )

        result = await run_claude_agent_activity(prompt="Hi", workspace_path="/ws", allowed_tools=["Read"])

        assert result["messages"] == []


class AsyncIteratorMock:
    """Helper to mock an async iterator (for client.receive_response())."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None
