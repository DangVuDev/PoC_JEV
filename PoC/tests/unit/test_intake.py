import json

import pytest

from app.errors import ErrorCode, PipelineError
from app.pipeline.executor.registry import ProviderRegistry
from app.pipeline.intake import run_intake
from app.pipeline.tasks import get_task
from app.schemas.request import DecideRequest
from tests.conftest import make_settings
from tests.fixtures import P1_CSV_ROW, P1_INPUT, P2_INPUT, p1_request, p2_request


def _intake(task, payload, **overrides):
    return run_intake(get_task(task), DecideRequest(**payload), ProviderRegistry(make_settings(**overrides)))


def _error(task, payload, **overrides) -> PipelineError:
    with pytest.raises(PipelineError) as exc:
        _intake(task, payload, **overrides)
    return exc.value


def test_input_json_object_is_accepted():
    result = _intake("p1", p1_request("laya"))
    assert result.record.input == P1_INPUT
    assert result.model == "multilingual"


def test_full_csv_row_is_accepted_and_extra_fields_ignored():
    result = _intake("p1", {"service_platform": "laya", **P1_CSV_ROW, "options": {"threshold": 0.9}})
    assert result.record.input == P1_INPUT


def test_unknown_keys_inside_input_json_are_dropped():
    result = _intake("p1", p1_request("laya", {**P1_INPUT, "expected_relation": "and"}))
    assert "expected_relation" not in result.record.input


def test_model_comes_from_env():
    assert _intake("p1", p1_request("openrouter")).model == "respan/span-01-lite:free"
    assert _intake("p1", p1_request("laya"), DECISION_LAYA_DEFAULT_MODEL="typed-decisions").model == "typed-decisions"


def test_invalid_input_json_string():
    assert _error("p1", p1_request("laya", "{broken")).code == ErrorCode.INVALID_INPUT_JSON


def test_input_json_must_be_object():
    assert _error("p1", p1_request("laya", "[1, 2]")).code == ErrorCode.INVALID_INPUT_JSON


def test_missing_required_field():
    error = _error("p1", p1_request("laya", {**P1_INPUT, "left_condition": " "}))
    assert error.code == ErrorCode.MISSING_INPUT_FIELD and error.http_status == 422


def test_p2_duplicate_member_ids_rejected():
    data = json.loads(json.dumps(P2_INPUT))
    data["members"].append(dict(data["members"][0]))
    assert _error("p2", p2_request("laya", data)).code == ErrorCode.MISSING_INPUT_FIELD


def test_unknown_provider_is_400():
    error = _error("p1", p1_request("nope"))
    assert (error.code, error.http_status) == (ErrorCode.UNKNOWN_PROVIDER, 400)


def test_unconfigured_provider_is_503():
    error = _error("p1", p1_request("typesafe"))
    assert (error.code, error.http_status) == (ErrorCode.PROVIDER_NOT_CONFIGURED, 503)


def test_custom_provider_without_model_is_503():
    error = _error(
        "p1",
        p1_request("gw"),
        DECISION_ENABLED_PROVIDERS="gw",
        DECISION_GW_ENDPOINT="https://gw.test/decide",
        DECISION_GW_API_KEY="secret-key-123456",
    )
    assert error.code == ErrorCode.PROVIDER_NOT_CONFIGURED
