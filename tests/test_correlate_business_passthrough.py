"""SDK side of SGP_OBS_CORRELATE_BUSINESS: trace.py reads the env flag and passes
it into the sgp_obs Correlator, version-resiliently.

The gate BEHAVIOR lives in sgp_obs (Correlator + bridge); here we only prove the
SDK's construction pass-through: the env is parsed correctly and _build_correlator
never crashes even when the installed sgp_obs predates the parameter."""

import inspect

from agentex.lib.core.tracing.trace import _build_correlator, _correlate_business
from sgp_obs.traces.correlator import Correlator


def test_correlate_business_env_parsing(monkeypatch):
    monkeypatch.delenv("SGP_OBS_CORRELATE_BUSINESS", raising=False)
    assert _correlate_business() is True  # default on
    for falsey in ("false", "0", "no", "FALSE", " no "):
        monkeypatch.setenv("SGP_OBS_CORRELATE_BUSINESS", falsey)
        assert _correlate_business() is False
    for truthy in ("true", "1", "yes", "", "anything"):
        monkeypatch.setenv("SGP_OBS_CORRELATE_BUSINESS", truthy)
        assert _correlate_business() is True


def test_build_correlator_never_crashes():
    # Works whether or not the installed sgp_obs accepts the kwarg (version skew):
    # with the param -> honored; without -> TypeError fallback to no-arg form.
    assert isinstance(_build_correlator(), Correlator)


def test_build_correlator_passes_flag_when_supported(monkeypatch):
    supported = "correlate_business" in inspect.signature(Correlator.__init__).parameters
    if not supported:
        # Pinned sgp_obs predates the flag; nothing to assert beyond no-crash.
        assert isinstance(_build_correlator(), Correlator)
        return
    monkeypatch.setenv("SGP_OBS_CORRELATE_BUSINESS", "false")
    corr = _build_correlator()
    # the flag reached the Correlator instance
    assert getattr(corr, "_correlate_business") is False
