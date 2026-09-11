from datetime import UTC, datetime

from agentex.lib.types.tracing import Span


def _span(**extra) -> Span:
    return Span(id="s1", name="n", trace_id="t1", start_time=datetime(2026, 1, 1, tzinfo=UTC), **extra)


def test_unknown_keys_survive_validation_and_a_json_round_trip():
    span = Span.model_validate({**_span().model_dump(), "extension": {"sampled": True}})

    assert span.extension == {"sampled": True}  # type: ignore[attr-defined]
    assert Span.model_validate_json(span.model_dump_json()).model_dump()["extension"] == {"sampled": True}


def test_processors_can_attach_their_own_attributes():
    span = _span()
    span.annotation = "custom"  # type: ignore[attr-defined]

    assert span.model_copy(deep=True).model_dump()["annotation"] == "custom"
