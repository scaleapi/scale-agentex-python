"""Failure-check span attributes.

Keys and formats are literals from the check contract, never read back from the module under test.
"""

from __future__ import annotations

import json
import dataclasses
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from scale_gp_beta.lib.tracing import create_span as sgp_create_span

from agentex.lib import adk
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.core.tracing.trace import Trace, AsyncTrace
from agentex.lib.core.tracing.span_queue import AsyncSpanQueue
from agentex.lib.core.tracing.failure_attributes import (
    FailureCheckSpec,
    VerificationRule,
    escalates,
    output_name,
    verification_result,
)
from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
    SGPSyncTracingProcessor,
    SGPAsyncTracingProcessor,
)

MODULE = "agentex.lib.core.tracing.processors.sgp_tracing_processor"

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}, "confidence": {"type": "number", "minimum": 0.0}},
    "required": ["answer"],
}

CONTRACT = [
    ("required_outputs", ["answer", "citations"], "sgp.agent.required_outputs", ["answer", "citations"]),
    ("step_budget", 25, "sgp.agent.step_budget", 25),
    ("stop_reason", "completed", "sgp.agent.stop_reason", "completed"),
    (
        "verification",
        [VerificationRule("run_tests", "apply_patch")],
        "sgp.agent.verification",
        [{"step": "run_tests", "verifies": "apply_patch"}],
    ),
    (
        "escalation_channels",
        ["send_email.to", "page_oncall.team"],
        "sgp.agent.escalation_channels",
        ["send_email.to", "page_oncall.team"],
    ),
    ("quote_arguments", ["cite.quote"], "sgp.agent.quote_arguments", ["cite.quote"]),
    ("prompt_version", "v3", "sgp.agent.prompt_version", "v3"),
]

SCHEMA_KEY = "sgp.agent.output_schema"
FULL_SPEC = {**{field: value for field, value, _, _ in CONTRACT}, "output_schema": SCHEMA}
NATIVE_ATTRIBUTES = {key: expected for _, _, key, expected in CONTRACT}


class TestRootSpanAttributes:
    @pytest.mark.parametrize(("field", "value", "key", "expected"), CONTRACT, ids=[row[0] for row in CONTRACT])
    def test_each_attribute_renders_its_documented_key_and_format(self, field, value, key, expected):
        attributes = FailureCheckSpec(**{field: value}).attributes()
        assert attributes == {key: expected}
        assert type(attributes[key]) is type(expected)

    def test_output_schema_is_written_as_json_text_that_decodes_to_the_schema(self):
        attributes = FailureCheckSpec(output_schema=SCHEMA).attributes()
        assert list(attributes) == [SCHEMA_KEY]
        assert type(attributes[SCHEMA_KEY]) is str
        assert json.loads(attributes[SCHEMA_KEY]) == SCHEMA

    def test_all_attributes_render_together_without_colliding(self):
        attributes = FailureCheckSpec(**FULL_SPEC).attributes()
        assert json.loads(attributes.pop(SCHEMA_KEY)) == SCHEMA
        assert attributes == NATIVE_ATTRIBUTES

    def test_every_field_is_optional_and_undeclared_ones_are_absent(self):
        assert FailureCheckSpec().attributes() == {}
        assert FailureCheckSpec(step_budget=3).attributes() == {"sgp.agent.step_budget": 3}

    def test_an_empty_list_declares_none_and_is_kept(self):
        attributes = FailureCheckSpec(required_outputs=[], escalation_channels=()).attributes()
        assert attributes == {"sgp.agent.required_outputs": [], "sgp.agent.escalation_channels": []}

    def test_rendered_data_survives_a_json_round_trip(self):
        attributes = FailureCheckSpec(**FULL_SPEC).attributes()
        assert json.loads(json.dumps(attributes)) == attributes

    def test_the_spec_is_frozen(self):
        spec = FailureCheckSpec(step_budget=3)
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.step_budget = 4  # type: ignore[misc]

    def test_specs_with_a_schema_stay_hashable_and_compare_by_value(self):
        first = FailureCheckSpec(required_outputs=["a"], output_schema=SCHEMA)
        second = FailureCheckSpec(required_outputs=("a",), output_schema=dict(SCHEMA))
        assert first == second
        assert hash(first) == hash(second)
        assert first != FailureCheckSpec(required_outputs=["a"], output_schema={"type": "string"})

    def test_fields_are_keyword_only(self):
        with pytest.raises(TypeError):
            FailureCheckSpec(["answer"])  # type: ignore[misc]

    def test_later_changes_to_inputs_or_rendered_data_do_not_reach_the_spec(self):
        outputs = ["answer"]
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        spec = FailureCheckSpec(required_outputs=outputs, output_schema=schema)

        outputs.append("sneaky")
        schema["properties"]["a"]["type"] = "number"
        spec.attributes()["sgp.agent.required_outputs"].append("sneaky")

        again = spec.attributes()
        assert again["sgp.agent.required_outputs"] == ["answer"]
        assert json.loads(again[SCHEMA_KEY]) == {"type": "object", "properties": {"a": {"type": "string"}}}

    def test_replace_adds_the_stop_reason_known_only_at_the_end(self):
        spec = FailureCheckSpec(required_outputs=["answer"])
        done = dataclasses.replace(spec, stop_reason="completed")
        assert done.attributes() == {
            "sgp.agent.required_outputs": ["answer"],
            "sgp.agent.stop_reason": "completed",
        }

    def test_replace_validates_again(self):
        with pytest.raises(ValueError, match="positive integer"):
            dataclasses.replace(FailureCheckSpec(step_budget=3), step_budget=0)


class TestRootSpanValidation:
    NESTING_DEPTH_PAST_RECURSION_LIMIT = 200_000

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"required_outputs": ["answer", "answer"]}, "duplicate entry 'answer'"),
            ({"required_outputs": [""]}, "non-empty string"),
            ({"required_outputs": ["  "]}, "non-empty string"),
            ({"required_outputs": [3]}, "non-empty string"),
            ({"required_outputs": [None]}, "non-empty string"),
            ({"required_outputs": [" answer"]}, "leading or trailing whitespace"),
            ({"required_outputs": ["answer\n"]}, "leading or trailing whitespace"),
            ({"required_outputs": "answer"}, "list of strings"),
            ({"required_outputs": {"answer"}}, "list of strings"),
            ({"required_outputs": 3}, "list of strings"),
            ({"required_outputs": b"answer"}, "list of strings"),
        ],
    )
    def test_required_outputs(self, kwargs, message):
        with pytest.raises(ValueError, match=message) as raised:
            FailureCheckSpec(**kwargs)
        assert str(raised.value).startswith("required_outputs ")

    @pytest.mark.parametrize("value", [0, -3, True, False, 2.5, "5", [5]])
    def test_step_budget_must_be_a_positive_integer(self, value):
        with pytest.raises(ValueError, match="step_budget must be a positive integer"):
            FailureCheckSpec(step_budget=value)

    @pytest.mark.parametrize("field", ["stop_reason", "prompt_version"])
    @pytest.mark.parametrize(
        ("value", "message"),
        [
            ("", "non-empty string"),
            ("   ", "non-empty string"),
            (7, "non-empty string"),
            (" v3", "leading or trailing whitespace"),
            ("v3\n", "leading or trailing whitespace"),
        ],
    )
    def test_free_text_fields(self, field, value, message):
        with pytest.raises(ValueError, match=message) as raised:
            FailureCheckSpec(**{field: value})
        assert str(raised.value).startswith(field)

    @pytest.mark.parametrize(
        ("value", "message"),
        [
            (["run_tests"], "entries must be VerificationRule"),
            ([{"step": "run_tests", "verifies": "apply_patch"}], "entries must be VerificationRule"),
            ("run_tests", "list of VerificationRule"),
            (VerificationRule("a", "b"), "list of VerificationRule"),
            ([VerificationRule("a", "b"), VerificationRule("a", "b")], "duplicate rule"),
        ],
    )
    def test_verification(self, value, message):
        with pytest.raises(ValueError, match=message) as raised:
            FailureCheckSpec(verification=value)
        assert str(raised.value).startswith("verification ")

    def test_one_step_may_verify_several_things_and_one_thing_have_several_verifiers(self):
        rules = [VerificationRule("check", "a"), VerificationRule("check", "b"), VerificationRule("recheck", "a")]
        assert len(FailureCheckSpec(verification=rules).attributes()["sgp.agent.verification"]) == 3

    @pytest.mark.parametrize("field", ["escalation_channels", "quote_arguments"])
    @pytest.mark.parametrize(
        ("value", "message"),
        [
            (["send_email"], "must look like tool.argument"),
            ([".to"], "must look like tool.argument"),
            (["send_email."], "must look like tool.argument"),
            (["send_email.to.cc"], "must look like tool.argument"),
            (["send_email..to"], "must look like tool.argument"),
            (["send email.to"], "must look like tool.argument"),
            (["send_email.to", "send_email.to"], "duplicate entry 'send_email.to'"),
            (["send_email.to", ""], "non-empty string"),
            ("send_email.to", "list of strings"),
        ],
    )
    def test_tool_argument_paths(self, field, value, message):
        with pytest.raises(ValueError, match=message) as raised:
            FailureCheckSpec(**{field: value})
        assert str(raised.value).startswith(f"{field} ")

    @pytest.mark.parametrize("field", ["escalation_channels", "quote_arguments"])
    @pytest.mark.parametrize("path", ["send_email.to.cc", "a.b.c.d"])
    def test_nested_argument_paths_are_rejected_and_the_error_says_so(self, field, path):
        with pytest.raises(ValueError, match="nested argument paths are not supported") as raised:
            FailureCheckSpec(**{field: [path]})
        assert str(raised.value).startswith(f"{field} entry must look like tool.argument")
        assert repr(path) in str(raised.value)

    @pytest.mark.parametrize("path", ["send_email", ".to", "send_email.", "send email.to"])
    def test_a_path_that_is_not_nested_is_not_blamed_on_nesting(self, path):
        with pytest.raises(ValueError, match="must look like tool.argument") as raised:
            FailureCheckSpec(escalation_channels=[path])
        assert "nested" not in str(raised.value)

    @pytest.mark.parametrize(
        ("value", "message"),
        [
            ([], "must be a JSON object"),
            ("{}", "must be a JSON object"),
            (True, "must be a JSON object"),
            ({"type": {"string"}}, "must be JSON serializable"),
            ({"minimum": float("nan")}, "must be JSON serializable"),
            ({"maximum": float("inf")}, "must be JSON serializable"),
            ({"x": object()}, "must be JSON serializable"),
        ],
    )
    def test_output_schema_must_be_a_json_object(self, value, message):
        with pytest.raises(ValueError, match=message) as raised:
            FailureCheckSpec(output_schema=value)
        assert str(raised.value).startswith("output_schema ")

    @pytest.mark.parametrize(
        "schema",
        [
            {1: "a"},
            {1: "a", "1": "b"},
            {True: "a"},
            {None: "a"},
            {1.5: "a"},
            {"properties": {2: {"type": "string"}}},
            {"anyOf": [{"properties": {3: {}}}]},
        ],
        ids=["int", "int-collides-with-str", "bool", "none", "float", "nested", "nested-in-list"],
    )
    def test_output_schema_keys_must_be_strings(self, schema):
        with pytest.raises(ValueError, match="keys must be strings") as raised:
            FailureCheckSpec(output_schema=schema)
        assert str(raised.value).startswith("output_schema ")

    def test_a_non_string_key_added_after_construction_fails_the_way_construction_does(self):
        with pytest.raises(ValueError) as at_construction:
            FailureCheckSpec(output_schema={1: "a"})

        spec = FailureCheckSpec(output_schema={"type": "object"})
        assert spec.output_schema is not None
        spec.output_schema[1] = "a"
        with pytest.raises(ValueError) as at_render:
            spec.attributes()
        assert str(at_render.value) == str(at_construction.value)

    def test_a_circular_schema_is_rejected(self):
        schema: dict[str, Any] = {"type": "object"}
        schema["self"] = schema
        with pytest.raises(ValueError, match="must be JSON serializable"):
            FailureCheckSpec(output_schema=schema)

    def test_a_pathologically_deep_schema_is_rejected(self):
        deep: list[Any] = []
        for _ in range(self.NESTING_DEPTH_PAST_RECURSION_LIMIT):
            deep = [deep]
        with pytest.raises(ValueError, match="must be JSON serializable"):
            FailureCheckSpec(output_schema={"default": deep})

    @pytest.mark.parametrize(
        "edit", [float("nan"), float("inf"), {"a", "b"}, object()], ids=["nan", "inf", "set", "object"]
    )
    def test_a_schema_edited_after_construction_fails_the_way_construction_does(self, edit):
        with pytest.raises(ValueError) as at_construction:
            FailureCheckSpec(output_schema={"edited": edit})

        spec = FailureCheckSpec(output_schema={"edited": 0})
        assert spec.output_schema is not None
        spec.output_schema["edited"] = edit
        with pytest.raises(ValueError) as at_render:
            spec.attributes()
        assert str(at_render.value) == str(at_construction.value)

    def test_an_empty_schema_is_a_json_object(self):
        attributes = FailureCheckSpec(output_schema={}).attributes()
        assert json.loads(attributes[SCHEMA_KEY]) == {}


class TestVerificationRule:
    @pytest.mark.parametrize(
        ("step", "verifies", "named"),
        [
            ("", "a", "verification step"),
            ("a", "", "verification verifies"),
            (" ", "a", "verification step"),
            ("a", None, "verification verifies"),
            (None, "a", "verification step"),
            (" a", "b", "verification step"),
        ],
    )
    def test_both_names_must_be_non_empty_strings(self, step, verifies, named):
        with pytest.raises(ValueError) as raised:
            VerificationRule(step, verifies)
        assert str(raised.value).startswith(f"{named} ")

    def test_rules_are_frozen(self):
        rule = VerificationRule("check", "answer")
        with pytest.raises(dataclasses.FrozenInstanceError):
            rule.step = "other"  # type: ignore[misc]


class TestPerSpanAttributes:
    def test_output_name(self):
        assert output_name("answer") == {"sgp.agent.output_name": "answer"}

    @pytest.mark.parametrize("value", ["", "  ", None, 3, " answer", "answer "])
    def test_output_name_rejects_bad_names(self, value):
        with pytest.raises(ValueError, match="output name"):
            output_name(value)

    @pytest.mark.parametrize("result", ["pass", "fail"])
    def test_verification_result(self, result):
        assert verification_result(result) == {"sgp.agent.verification_result": result}

    @pytest.mark.parametrize("value", ["PASS", "passed", "ok", "", None, True, False, 1])
    def test_verification_result_accepts_only_pass_or_fail(self, value):
        with pytest.raises(ValueError, match="'pass' or 'fail'"):
            verification_result(value)

    def test_escalates(self):
        assert escalates("3f2c1a9e-0000-4000-8000-000000000001") == {
            "sgp.agent.escalates": "3f2c1a9e-0000-4000-8000-000000000001"
        }

    @pytest.mark.parametrize("value", ["", "  ", None, 3, " span-1"])
    def test_escalates_rejects_bad_span_ids(self, value):
        with pytest.raises(ValueError, match="verification span id") as raised:
            escalates(value)
        assert str(raised.value).startswith("escalates ")

    def test_results_merge_into_a_span_data_dict(self):
        data = {"note": "kept", **output_name("answer")}
        assert data == {"note": "kept", "sgp.agent.output_name": "answer"}


class TestExports:
    def test_adk_exposes_the_helper(self):
        assert adk.FailureCheckSpec is FailureCheckSpec
        assert adk.VerificationRule is VerificationRule
        assert adk.failure_attributes.output_name is output_name
        assert adk.failure_attributes.verification_result is verification_result
        assert adk.failure_attributes.escalates is escalates
        assert {"failure_attributes", "FailureCheckSpec", "VerificationRule"} <= set(adk.__all__)


AGENT_ENV = MagicMock(ACP_TYPE="async", AGENT_NAME="pilot-agent", AGENT_ID="agent-1", AGENT_VERSION="sha-abc1234")
CONFIG = SGPTracingProcessorConfig(sgp_api_key="test-key", sgp_account_id="test-account")

SPEC_KWARGS = {field: value for field, value in FULL_SPEC.items() if field != "stop_reason"}
EXPECTED_ROOT = {**NATIVE_ATTRIBUTES, "sgp.agent.stop_reason": "budget_exhausted"}


def _offline_create_span(created: list[Any]):
    def create(**kwargs: Any):
        span = sgp_create_span(**kwargs, queue_manager=MagicMock())
        created.append(span)
        return span

    return create


def _assert_attributes_landed_in_sgp_metadata(items: list[dict[str, Any]]) -> None:
    by_name = {item["name"]: item for item in items}
    assert sorted(by_name) == ["agent", "answer", "escalate", "verify"]

    root = by_name["agent"]["metadata"]
    declared = {key: value for key, value in root.items() if key.startswith("sgp.agent.")}
    assert type(declared[SCHEMA_KEY]) is str
    assert json.loads(declared.pop(SCHEMA_KEY)) == SCHEMA
    assert declared == EXPECTED_ROOT
    assert "sgp" not in root
    assert root["__agent_version__"] == "sha-abc1234"

    assert by_name["answer"]["metadata"]["sgp.agent.output_name"] == "answer"
    assert by_name["verify"]["metadata"]["sgp.agent.verification_result"] == "fail"
    assert by_name["escalate"]["metadata"]["sgp.agent.escalates"] == by_name["verify"]["id"]

    for item in items:
        assert json.loads(json.dumps(item["metadata"])) == item["metadata"]


class TestRealSpanPath:
    async def test_async_tracer_delivers_attributes_as_flat_keys_with_native_values(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "1")
        client = MagicMock()
        client.spans.upsert_batch = AsyncMock()
        mock_env = MagicMock()
        mock_env.refresh.return_value = AGENT_ENV
        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(f"{MODULE}.AsyncSGPClient", return_value=client):
            processor = SGPAsyncTracingProcessor(CONFIG)
        processor._get_client = lambda: client  # type: ignore[method-assign]

        queue = AsyncSpanQueue()
        trace = AsyncTrace(processors=[processor], client=MagicMock(), trace_id="trace-1", span_queue=queue)
        spec = FailureCheckSpec(**SPEC_KWARGS)

        with patch(f"{MODULE}.create_span", side_effect=_offline_create_span([])):
            async with trace.span(name="agent", data=spec.attributes()) as root:
                async with trace.span(name="answer", parent_id=root.id, data=output_name("answer")):
                    pass
                async with trace.span(name="verify", parent_id=root.id, data=verification_result("fail")) as verify:
                    pass
                async with trace.span(name="escalate", parent_id=root.id, data=escalates(verify.id)):
                    pass
                stopped = dataclasses.replace(spec, stop_reason="budget_exhausted")
                assert isinstance(root.data, dict)
                root.data = {**root.data, **stopped.attributes()}
            await queue.shutdown()

        items = [item for call in client.spans.upsert_batch.call_args_list for item in call.kwargs["items"]]
        _assert_attributes_landed_in_sgp_metadata(items)

    def test_sync_tracer_delivers_attributes_as_flat_keys_with_native_values(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "1")
        mock_env = MagicMock()
        mock_env.refresh.return_value = AGENT_ENV
        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(f"{MODULE}.SGPClient"), patch(
            f"{MODULE}.tracing"
        ):
            processor = SGPSyncTracingProcessor(CONFIG)

        created: list[Any] = []
        trace = Trace(processors=[processor], client=MagicMock(), trace_id="trace-1")
        spec = FailureCheckSpec(**SPEC_KWARGS)

        with patch(f"{MODULE}.create_span", side_effect=_offline_create_span(created)):
            with trace.span(name="agent", data=spec.attributes()) as root:
                with trace.span(name="answer", parent_id=root.id, data=output_name("answer")):
                    pass
                with trace.span(name="verify", parent_id=root.id, data=verification_result("fail")) as verify:
                    pass
                with trace.span(name="escalate", parent_id=root.id, data=escalates(verify.id)):
                    pass
                stopped = dataclasses.replace(spec, stop_reason="budget_exhausted")
                assert isinstance(root.data, dict)
                root.data = {**root.data, **stopped.attributes()}

        _assert_attributes_landed_in_sgp_metadata([span.to_request_params() for span in created])
