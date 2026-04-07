"""Tests for Claude Agents SDK streaming hooks.

These tests validate the TemporalStreamingHooks class and
create_streaming_hooks factory from the hooks module.
"""

from __future__ import annotations

import sys
import importlib.util
from types import ModuleType
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk.types import HookMatcher

# ---------------------------------------------------------------------------
# Module loading: same technique as test_claude_agents_activities.py
# We load hooks.py directly to avoid triggering the plugins __init__.py chain
# which pulls in langchain_core/langgraph (optional deps).
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parents[2] / "src"
_HOOKS_PATH = _SRC / "agentex" / "lib" / "core" / "temporal" / "plugins" / "claude_agents" / "hooks" / "hooks.py"

# Stub external modules that hooks.py imports so the module can load.
for _name in ["agentex.lib.adk", "agentex.lib.utils.logging"]:
    sys.modules.setdefault(_name, MagicMock())

# Ensure parent packages exist so the dotted path resolves
for _pkg in [
    "agentex",
    "agentex.lib",
    "agentex.lib.core",
    "agentex.lib.core.temporal",
    "agentex.lib.core.temporal.plugins",
    "agentex.lib.core.temporal.plugins.claude_agents",
    "agentex.lib.core.temporal.plugins.claude_agents.hooks",
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = []  # type: ignore[attr-defined]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod

# Real pydantic types — importable without triggering the problematic chain.
from agentex.types.tool_response_content import ToolResponseContent  # noqa: E402

# Load the hooks module directly
_spec = importlib.util.spec_from_file_location(
    "agentex.lib.core.temporal.plugins.claude_agents.hooks.hooks",
    _HOOKS_PATH,
)
assert _spec is not None and _spec.loader is not None
_hooks_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _hooks_mod
_spec.loader.exec_module(_hooks_mod)

TemporalStreamingHooks = _hooks_mod.TemporalStreamingHooks
create_streaming_hooks = _hooks_mod.create_streaming_hooks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AsyncCtxManager:
    """Simple async context manager that yields a given value."""

    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        pass


def _make_adk_mock():
    """Create a fresh adk mock with streaming context manager wired up.

    Returns (adk_mock, tool_ctx) where tool_ctx is the mock yielded by
    `async with adk.streaming.streaming_task_message_context(...)`.
    """
    tool_ctx = AsyncMock()
    tool_ctx.task_message = MagicMock(name="task_message")
    tool_ctx.stream_update = AsyncMock()

    adk_mock = MagicMock()
    adk_mock.streaming.streaming_task_message_context.return_value = _AsyncCtxManager(tool_ctx)
    return adk_mock, tool_ctx


def _make_post_tool_input(tool_name: str, tool_use_id: str, tool_response: str = "") -> dict:
    """Build a HookInput dict for PostToolUse."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "tool_response": tool_response,
    }


def _make_failure_input(tool_name: str, tool_use_id: str, error: str) -> dict:
    """Build a HookInput dict for PostToolUseFailure."""
    return {
        "hook_event_name": "PostToolUseFailure",
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Tests: TemporalStreamingHooks.__init__
# ---------------------------------------------------------------------------


class TestTemporalStreamingHooksInit:
    def test_stores_task_id(self):
        hooks = TemporalStreamingHooks(task_id="task-1")
        assert hooks.task_id == "task-1"

    def test_stores_trace_and_parent_span(self):
        hooks = TemporalStreamingHooks(task_id="task-1", trace_id="trace-1", parent_span_id="span-1")
        assert hooks.trace_id == "trace-1"
        assert hooks.parent_span_id == "span-1"

    def test_defaults_to_none(self):
        hooks = TemporalStreamingHooks(task_id=None)
        assert hooks.task_id is None
        assert hooks.trace_id is None
        assert hooks.parent_span_id is None

    def test_subagent_spans_initialized_empty(self):
        hooks = TemporalStreamingHooks(task_id="task-1")
        assert hooks.subagent_spans == {}

    def test_accepts_shared_subagent_spans(self):
        shared = {"tu-1": ("ctx", "span")}
        hooks = TemporalStreamingHooks(task_id="task-1", subagent_spans=shared)
        assert hooks.subagent_spans is shared


# ---------------------------------------------------------------------------
# Tests: auto_allow_hook (PreToolUse)
# ---------------------------------------------------------------------------


class TestAutoAllowHook:
    @pytest.mark.asyncio
    async def test_returns_allow_decision(self):
        hooks = TemporalStreamingHooks(task_id="task-1")
        result = await hooks.auto_allow_hook(
            _input_data={},
            _tool_use_id="tu-1",
            _context=None,
        )
        assert result["continue_"] is True
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    @pytest.mark.asyncio
    async def test_works_without_task_id(self):
        hooks = TemporalStreamingHooks(task_id=None)
        result = await hooks.auto_allow_hook(
            _input_data={},
            _tool_use_id=None,
            _context=None,
        )
        assert result["continue_"] is True


# ---------------------------------------------------------------------------
# Tests: post_tool_use_hook (PostToolUse)
# ---------------------------------------------------------------------------


class TestPostToolUseHook:
    @pytest.mark.asyncio
    async def test_skips_wrong_event_name(self):
        hooks = TemporalStreamingHooks(task_id="task-1")
        result = await hooks.post_tool_use_hook(
            input_data={"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_use_id": "tu-1"},
            _tool_use_id="tu-1",
            _context=None,
        )
        assert result["continue_"] is True

    @pytest.mark.asyncio
    async def test_skips_when_no_task_id(self):
        hooks = TemporalStreamingHooks(task_id=None)
        result = await hooks.post_tool_use_hook(
            input_data=_make_post_tool_input("Read", "tu-1", "contents"),
            _tool_use_id="tu-1",
            _context=None,
        )
        assert result["continue_"] is True

    @pytest.mark.asyncio
    async def test_streams_tool_response(self):
        adk_mock, _ = _make_adk_mock()

        hooks = TemporalStreamingHooks(task_id="task-1")
        with patch.object(_hooks_mod, "adk", adk_mock):
            result = await hooks.post_tool_use_hook(
                input_data=_make_post_tool_input("Read", "tu-1", "file contents"),
                _tool_use_id="tu-1",
                _context=None,
            )

        assert result["continue_"] is True
        adk_mock.streaming.streaming_task_message_context.assert_called_once()
        call_kwargs = adk_mock.streaming.streaming_task_message_context.call_args.kwargs
        assert call_kwargs["task_id"] == "task-1"
        assert isinstance(call_kwargs["initial_content"], ToolResponseContent)
        assert call_kwargs["initial_content"].name == "Read"
        assert call_kwargs["initial_content"].content == "file contents"
        assert call_kwargs["initial_content"].tool_call_id == "tu-1"

    @pytest.mark.asyncio
    async def test_closes_subagent_span(self):
        adk_mock, _ = _make_adk_mock()

        span_mock = MagicMock()
        span_ctx = AsyncMock()
        span_ctx.__aexit__ = AsyncMock(return_value=False)

        subagent_spans = {"tu-sub-1": (span_ctx, span_mock)}
        hooks = TemporalStreamingHooks(task_id="task-1", subagent_spans=subagent_spans)

        with patch.object(_hooks_mod, "adk", adk_mock):
            await hooks.post_tool_use_hook(
                input_data=_make_post_tool_input("Task", "tu-sub-1", "result"),
                _tool_use_id="tu-sub-1",
                _context=None,
            )

        assert span_mock.output == {"result": "result"}
        span_ctx.__aexit__.assert_awaited_once_with(None, None, None)
        assert "tu-sub-1" not in subagent_spans

    @pytest.mark.asyncio
    async def test_streaming_failure_does_not_raise(self):
        adk_mock = MagicMock()
        adk_mock.streaming.streaming_task_message_context.side_effect = RuntimeError("down")

        hooks = TemporalStreamingHooks(task_id="task-1")
        with patch.object(_hooks_mod, "adk", adk_mock):
            result = await hooks.post_tool_use_hook(
                input_data=_make_post_tool_input("Bash", "tu-1", "output"),
                _tool_use_id="tu-1",
                _context=None,
            )
        assert result["continue_"] is True


# ---------------------------------------------------------------------------
# Tests: post_tool_use_failure_hook (PostToolUseFailure)
# ---------------------------------------------------------------------------


class TestPostToolUseFailureHook:
    @pytest.mark.asyncio
    async def test_skips_wrong_event_name(self):
        hooks = TemporalStreamingHooks(task_id="task-1")
        result = await hooks.post_tool_use_failure_hook(
            input_data={"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_use_id": "tu-1"},
            _tool_use_id="tu-1",
            _context=None,
        )
        assert result["continue_"] is True

    @pytest.mark.asyncio
    async def test_skips_when_no_task_id(self):
        hooks = TemporalStreamingHooks(task_id=None)
        result = await hooks.post_tool_use_failure_hook(
            input_data=_make_failure_input("Read", "tu-1", "permission denied"),
            _tool_use_id="tu-1",
            _context=None,
        )
        assert result["continue_"] is True

    @pytest.mark.asyncio
    async def test_streams_error_response(self):
        adk_mock, _ = _make_adk_mock()

        hooks = TemporalStreamingHooks(task_id="task-1")
        with patch.object(_hooks_mod, "adk", adk_mock):
            result = await hooks.post_tool_use_failure_hook(
                input_data=_make_failure_input("Bash", "tu-1", "command not found"),
                _tool_use_id="tu-1",
                _context=None,
            )

        assert result["continue_"] is True
        adk_mock.streaming.streaming_task_message_context.assert_called_once()
        call_kwargs = adk_mock.streaming.streaming_task_message_context.call_args.kwargs
        assert call_kwargs["task_id"] == "task-1"
        assert isinstance(call_kwargs["initial_content"], ToolResponseContent)
        assert call_kwargs["initial_content"].name == "Bash"
        assert call_kwargs["initial_content"].content == "Error: command not found"
        assert call_kwargs["initial_content"].tool_call_id == "tu-1"

    @pytest.mark.asyncio
    async def test_closes_subagent_span_on_failure(self):
        adk_mock, _ = _make_adk_mock()

        span_mock = MagicMock()
        span_ctx = AsyncMock()
        span_ctx.__aexit__ = AsyncMock(return_value=False)

        subagent_spans = {"tu-sub-1": (span_ctx, span_mock)}
        hooks = TemporalStreamingHooks(task_id="task-1", subagent_spans=subagent_spans)

        with patch.object(_hooks_mod, "adk", adk_mock):
            await hooks.post_tool_use_failure_hook(
                input_data=_make_failure_input("Task", "tu-sub-1", "timeout"),
                _tool_use_id="tu-sub-1",
                _context=None,
            )

        assert span_mock.output == {"error": "timeout"}
        span_ctx.__aexit__.assert_awaited_once_with(None, None, None)
        assert "tu-sub-1" not in subagent_spans

    @pytest.mark.asyncio
    async def test_streaming_failure_does_not_raise(self):
        adk_mock = MagicMock()
        adk_mock.streaming.streaming_task_message_context.side_effect = RuntimeError("down")

        hooks = TemporalStreamingHooks(task_id="task-1")
        with patch.object(_hooks_mod, "adk", adk_mock):
            result = await hooks.post_tool_use_failure_hook(
                input_data=_make_failure_input("Bash", "tu-1", "oops"),
                _tool_use_id="tu-1",
                _context=None,
            )
        assert result["continue_"] is True


# ---------------------------------------------------------------------------
# Tests: create_streaming_hooks factory
# ---------------------------------------------------------------------------


class TestCreateStreamingHooks:
    def test_returns_all_three_hook_events(self):
        result = create_streaming_hooks(task_id="task-1")
        assert "PreToolUse" in result
        assert "PostToolUse" in result
        assert "PostToolUseFailure" in result

    def test_each_key_has_one_hook_matcher(self):
        result = create_streaming_hooks(task_id="task-1")
        for key in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            assert len(result[key]) == 1
            assert isinstance(result[key][0], HookMatcher)

    def test_matchers_match_all_tools(self):
        result = create_streaming_hooks(task_id="task-1")
        for key in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            assert result[key][0].matcher is None

    def test_hooks_are_callable(self):
        result = create_streaming_hooks(task_id="task-1")
        for key in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            assert len(result[key][0].hooks) == 1
            assert callable(result[key][0].hooks[0])

    def test_all_hooks_share_same_instance(self):
        result = create_streaming_hooks(task_id="task-1", trace_id="trace-1", parent_span_id="span-1")
        instances = {result[key][0].hooks[0].__self__ for key in ("PreToolUse", "PostToolUse", "PostToolUseFailure")}
        assert len(instances) == 1
        instance = instances.pop()
        assert instance.task_id == "task-1"
        assert instance.trace_id == "trace-1"
        assert instance.parent_span_id == "span-1"

    def test_passes_shared_subagent_spans(self):
        shared = {}
        result = create_streaming_hooks(task_id="task-1", subagent_spans=shared)
        instance = result["PreToolUse"][0].hooks[0].__self__
        assert instance.subagent_spans is shared

    def test_none_task_id_still_creates_hooks(self):
        result = create_streaming_hooks(task_id=None)
        assert "PreToolUse" in result
