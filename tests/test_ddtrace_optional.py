"""ddtrace is an optional dependency (the ``datadog`` extra).

Some deployments do not allow Datadog software to be installed, so the SDK has to
import and log cleanly without it. These tests hide ddtrace via ``sys.modules`` (a
``None`` entry makes the import raise ImportError) and check that nothing breaks.
"""

from __future__ import annotations

import os
import sys
import json
import logging
import subprocess

import pytest

from agentex.lib.utils import logging as agentex_logging
from agentex.lib.core.tracing import obs_ids, obs_span


def _hide_ddtrace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "ddtrace", None)
    monkeypatch.setitem(sys.modules, "ddtrace.trace", None)


def _format(formatter: logging.Formatter) -> dict:
    record = logging.LogRecord("agentex.test", logging.INFO, __file__, 1, "hello", None, None)
    return json.loads(formatter.format(record))


# A fresh interpreter, so the import-time `import ddtrace` in agentex modules runs
# with ddtrace hidden rather than reusing the copy this test process already loaded.
_IMPORT_WITHOUT_DDTRACE = """
import sys, logging
sys.modules["ddtrace"] = None

import agentex
from agentex.lib.utils import logging as agentex_logging
import agentex.lib.adk
import agentex.lib.sdk.fastacp.fastacp
import agentex.lib.core.tracing.trace
import agentex.lib.cli.commands.main

assert agentex_logging.ddtrace is None
record = logging.LogRecord("agentex.test", logging.INFO, "test.py", 1, "hello", None, None)
print(agentex_logging.CustomJSONFormatter().format(record))
"""


def test_agentex_imports_and_logs_without_ddtrace() -> None:
    env = {"DD_AGENT_HOST": "localhost", "DD_SERVICE": "svc", "DD_ENV": "test", "DD_VERSION": "1.2.3"}
    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_WITHOUT_DDTRACE],
        capture_output=True,
        text=True,
        env={**{k: v for k, v in os.environ.items() if not k.startswith("DD_")}, **env},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["message"] == "hello"
    assert "dd.trace_id" not in payload
    assert "dd.span_id" not in payload
    # The env-var fallbacks still apply without ddtrace.
    assert payload["dd.service"] == "svc"
    assert payload["dd.env"] == "test"
    assert payload["dd.version"] == "1.2.3"


class TestJsonFormatter:
    def test_without_ddtrace_skips_trace_ids_and_keeps_env_fallbacks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(agentex_logging, "ddtrace", None)
        monkeypatch.setattr(agentex_logging, "_is_datadog_configured", True)
        monkeypatch.setenv("DD_SERVICE", "svc")
        monkeypatch.delenv("DD_ENV", raising=False)
        monkeypatch.delenv("DD_VERSION", raising=False)

        payload = _format(agentex_logging.CustomJSONFormatter())

        assert "dd.trace_id" not in payload
        assert "dd.span_id" not in payload
        assert payload["dd.service"] == "svc"
        assert "dd.env" not in payload

    def test_with_ddtrace_adds_trace_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pytest.importorskip("ddtrace")
        monkeypatch.setattr(agentex_logging, "_is_datadog_configured", True)

        payload = _format(agentex_logging.CustomJSONFormatter())

        assert "dd.trace_id" in payload
        assert "dd.span_id" in payload


class TestObsHelpersWithoutDdtrace:
    def test_ddtrace_ids_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _hide_ddtrace(monkeypatch)
        assert obs_ids._ddtrace_ids() is None

    def test_default_mode_correlation_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SGP_OBS_MODE", raising=False)  # default is dd_only
        _hide_ddtrace(monkeypatch)
        assert obs_ids.obs_correlation() == {}

    def test_default_mode_open_span_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SGP_OBS_MODE", raising=False)
        _hide_ddtrace(monkeypatch)
        assert obs_span.open_obs_span("step", "biz-span", "biz-trace") is None

    def test_tag_ambient_is_false_and_never_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SGP_OBS_MODE", raising=False)
        _hide_ddtrace(monkeypatch)
        assert obs_span._tag_ddtrace_ambient("biz-span", "biz-trace") is False
        obs_span.tag_ambient_obs_span("biz-span", "biz-trace")
