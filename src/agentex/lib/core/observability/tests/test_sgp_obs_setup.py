"""Tests for ``agentex.lib.core.observability.sgp_obs_setup``.

The property under test is that this can never hurt a caller: whatever the state of
sgp-obs or the environment, ``init_sgp_obs`` returns a status string and does not
raise, and ``shutdown_sgp_obs`` does not raise. Both gates get a test, plus the
failure modes, the two silent-misconfiguration warnings, and the flush.

These never import the real sgp-obs — it is absent in CI by design — so every test
installs a stand-in whose ``init`` is under the test's control.
"""

from __future__ import annotations

import sys
import builtins

import pytest

from agentex.lib.core.observability import sgp_obs_setup
from agentex.lib.core.observability.sgp_obs_setup import init_sgp_obs, shutdown_sgp_obs

_SWITCHES = (
    "SGP_OBS_ENABLED",
    "SGP_METRICS_DISABLED",
    "SGP_TRACES_DISABLED",
    "SGP_LOGS_DISABLED",
    "AGENT_NAME",
)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    """The status is cached process-wide, so every test starts from unset. The
    environment is cleared too: two code paths branch on the master switch, and a
    developer with SGP_OBS_ENABLED exported would otherwise flip those tests."""
    for name in _SWITCHES:
        monkeypatch.delenv(name, raising=False)
    sgp_obs_setup._reset_for_tests()
    yield
    sgp_obs_setup._reset_for_tests()


def _fake_sgp_obs(monkeypatch, init=None, shutdown=None):
    """Install a stand-in ``sgp_obs`` module whose entry points we control."""
    module = type(sys)("sgp_obs")
    module.init = init if init is not None else (lambda **_kwargs: {"metrics": object()})
    if shutdown is not None:
        module.shutdown = shutdown
    monkeypatch.setitem(sys.modules, "sgp_obs", module)
    return module


def _block_sgp_obs_import(monkeypatch, exc=None):
    monkeypatch.delitem(sys.modules, "sgp_obs", raising=False)
    real_import = builtins.__import__
    error = exc or ImportError("No module named 'sgp_obs'")

    def blocked(name, *args, **kwargs):
        if name == "sgp_obs" or name.startswith("sgp_obs."):
            raise error
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)


class TestGateOneSgpObsNotInstalled:
    def test_missing_package_is_reported_not_raised(self, monkeypatch):
        _block_sgp_obs_import(monkeypatch)
        assert init_sgp_obs() == "not_installed"

    def test_a_broken_install_does_not_stop_startup(self, monkeypatch):
        """An ImportError is ordinary; anything else is a broken install, not a
        missing one, and must still be swallowed."""
        _block_sgp_obs_import(monkeypatch, RuntimeError("half-installed wheel"))
        assert init_sgp_obs() == "error"

    def test_silence_is_expected_when_nobody_asked(self, monkeypatch, caplog):
        """sgp-obs is not a dependency, so absent-and-unasked-for is the normal
        case for every agent. It must not warn."""
        _block_sgp_obs_import(monkeypatch)
        with caplog.at_level("WARNING"):
            assert init_sgp_obs() == "not_installed"
        assert caplog.records == []

    def test_enabled_but_missing_says_what_to_install(self, monkeypatch, caplog):
        """The one case that must be loud: the operator asked for observability and
        the package is not there. Silence would look like working instrumentation."""
        monkeypatch.setenv("SGP_OBS_ENABLED", "true")
        _block_sgp_obs_import(monkeypatch)
        with caplog.at_level("WARNING"):
            assert init_sgp_obs() == "not_installed"
        assert len(caplog.records) == 1
        assert "sgp-obs is not installed" in caplog.text
        assert "genai-auto,http,otlp" in caplog.text


class TestGateTwoEnvironmentSwitches:
    def test_no_handles_means_disabled(self, monkeypatch):
        """sgp_obs.init() returns an empty dict when the master switch or every
        per-signal switch is off. That is the DEFAULT: sgp-obs installed, and
        recording nothing until someone sets the environment."""
        _fake_sgp_obs(monkeypatch, lambda **_kwargs: {})
        assert init_sgp_obs() == "disabled"

    def test_disabled_and_unasked_for_is_quiet(self, monkeypatch, caplog):
        _fake_sgp_obs(monkeypatch, lambda **_kwargs: {})
        with caplog.at_level("WARNING"):
            assert init_sgp_obs() == "disabled"
        assert caplog.records == []

    def test_master_switch_on_but_nothing_wired_names_the_variables(
        self, monkeypatch, caplog
    ):
        """sgp-obs 0.16.0 made every signal opt-in twice: the master switch plus an
        explicit *_DISABLED=false. So SGP_OBS_ENABLED on its own wires nothing and
        says nothing, which is the single easiest way to believe an agent is
        instrumented when it is not."""
        monkeypatch.setenv("SGP_OBS_ENABLED", "true")
        _fake_sgp_obs(monkeypatch, lambda **_kwargs: {})
        with caplog.at_level("WARNING"):
            assert init_sgp_obs() == "disabled"
        assert len(caplog.records) == 1
        for var in ("SGP_METRICS_DISABLED", "SGP_TRACES_DISABLED", "SGP_LOGS_DISABLED"):
            assert var in caplog.text

    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
    def test_master_switch_truthy_forms(self, monkeypatch, caplog, raw):
        """Matched to sgp_obs.env._TRUTHY, so this module's idea of "on" is the
        same as the library's. A mismatch would put the warning on the wrong side."""
        monkeypatch.setenv("SGP_OBS_ENABLED", raw)
        _fake_sgp_obs(monkeypatch, lambda **_kwargs: {})
        with caplog.at_level("WARNING"):
            init_sgp_obs()
        assert len(caplog.records) == 1

    def test_all_three_signals_are_named_in_the_status(self, monkeypatch):
        _fake_sgp_obs(
            monkeypatch,
            lambda **_kwargs: {"logs": object(), "metrics": object(), "traces": object()},
        )
        assert init_sgp_obs() == "wired:logs,metrics,traces"


class TestWhatIsPassedToSgpObs:
    @staticmethod
    def _capture(monkeypatch):
        seen = {}

        def capture(**kwargs):
            seen.update(kwargs)
            return {"metrics": object()}

        _fake_sgp_obs(monkeypatch, capture)
        return seen

    def test_app_reaches_sgp_obs(self, monkeypatch):
        """Passing the ACP server is what adds http.server.* for the agent's own
        entry point and installs the trace-context ingress, so it must not be
        silently dropped."""
        seen = self._capture(monkeypatch)
        sentinel = object()
        init_sgp_obs(app=sentinel)
        assert seen["app"] is sentinel

    def test_source_is_agentex(self, monkeypatch):
        """The SDK knows the runtime; an agent author would have to know to pass it.
        It is what stamps agent_id and task_id onto log records."""
        seen = self._capture(monkeypatch)
        init_sgp_obs()
        assert seen["source"] == "agentex"

    def test_agent_name_is_offered_as_the_service_name(self, monkeypatch):
        """sgp-obs fills OTEL_SERVICE_NAME from this only when the deployment left
        it unset; without either, every signal is attributed to "unknown"."""
        monkeypatch.setenv("AGENT_NAME", "compass-sleep-agent")
        seen = self._capture(monkeypatch)
        init_sgp_obs()
        assert seen["service_name"] == "compass-sleep-agent"

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_blank_agent_name_is_passed_as_none(self, monkeypatch, raw):
        """Blank is the Helm rendered-empty idiom. Forwarding "" would have sgp-obs
        set OTEL_SERVICE_NAME to an empty string rather than leave it alone."""
        monkeypatch.setenv("AGENT_NAME", raw)
        seen = self._capture(monkeypatch)
        init_sgp_obs()
        assert seen["service_name"] is None


class TestFailOpen:
    def test_an_exception_from_init_is_swallowed(self, monkeypatch):
        def boom(**_kwargs):
            raise ValueError("boom")

        _fake_sgp_obs(monkeypatch, boom)
        assert init_sgp_obs() == "error"

    def test_a_ci_logs_misconfiguration_still_does_not_stop_startup(self, monkeypatch):
        """sgp_obs.init has one deliberate exception to its own fail-open rule: under
        the CI variable, a logs misconfiguration raises. An agent must still serve."""

        def strict(**_kwargs):
            raise RuntimeError("MisconfigurationError: drop mode without an allowlist")

        _fake_sgp_obs(monkeypatch, strict)
        assert init_sgp_obs() == "error"

    def test_status_is_computed_once(self, monkeypatch):
        """A Temporal worker and an ACP server can both reach this in one process;
        sgp_obs.init() is not meant to run twice."""
        calls = []

        def counting(**kwargs):
            calls.append(kwargs)
            return {"metrics": object()}

        _fake_sgp_obs(monkeypatch, counting)
        assert init_sgp_obs() == "wired:metrics"
        assert init_sgp_obs() == "wired:metrics"
        assert len(calls) == 1


class TestShutdown:
    async def test_flushes_when_wired(self, monkeypatch):
        """Without this the periodic exporter's buffer is dropped when the pod
        stops, which for a short-lived agent can be most of what it recorded."""
        called = []
        _fake_sgp_obs(monkeypatch, shutdown=lambda: called.append(True))
        assert init_sgp_obs() == "wired:metrics"
        await shutdown_sgp_obs()
        assert called == [True]

    async def test_no_flush_when_never_wired(self, monkeypatch):
        called = []
        _fake_sgp_obs(
            monkeypatch, init=lambda **_kwargs: {}, shutdown=lambda: called.append(True)
        )
        assert init_sgp_obs() == "disabled"
        await shutdown_sgp_obs()
        assert called == []

    async def test_no_flush_before_init(self, monkeypatch):
        """Called from the lifespan's finally, which runs even if startup failed
        before the constructor's init_sgp_obs ever ran."""
        called = []
        _fake_sgp_obs(monkeypatch, shutdown=lambda: called.append(True))
        await shutdown_sgp_obs()
        assert called == []

    async def test_an_older_sgp_obs_without_shutdown_is_tolerated(self, monkeypatch):
        """shutdown() arrived in 0.16.0. This package declares no dependency on
        sgp-obs and so cannot set a floor, hence feature detection."""
        _fake_sgp_obs(monkeypatch)  # no shutdown attribute
        assert init_sgp_obs() == "wired:metrics"
        await shutdown_sgp_obs()  # must not raise

    async def test_a_failing_flush_does_not_fail_shutdown(self, monkeypatch):
        def boom():
            raise RuntimeError("exporter timed out")

        _fake_sgp_obs(monkeypatch, shutdown=boom)
        assert init_sgp_obs() == "wired:metrics"
        await shutdown_sgp_obs()  # must not raise


class TestAnAgentStillServesWithoutSgpObs:
    """Nitesh's verification item, startup half: an account not yet on the
    CodeArtifact allowlist gets an image with no ``sgp_obs`` in it. The gate
    returning ``not_installed`` is necessary but not sufficient — what has to hold
    is that the ACP server still constructs and still answers requests. This
    exercises the real constructor, which is where ``init_sgp_obs`` is called.
    """

    def test_acp_server_constructs_and_serves_healthz(self, monkeypatch):
        from fastapi.testclient import TestClient

        from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer

        # Import first, unpatched, so the deep FastACP dependency chain loads
        # cleanly; only sgp_obs is hidden, and only while the constructor runs.
        _block_sgp_obs_import(monkeypatch)

        server = BaseACPServer()
        assert sgp_obs_setup._status == "not_installed"

        # No `with`: that would run the lifespan, which registers the agent
        # against a live control plane.
        response = TestClient(server).get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_the_json_rpc_route_is_still_mounted(self, monkeypatch):
        """A server that answers /healthz but lost /api would pass a liveness probe
        and fail every actual request."""
        from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer

        _block_sgp_obs_import(monkeypatch)
        routes = {getattr(r, "path", None) for r in BaseACPServer().routes}
        assert {"/healthz", "/api"} <= routes
