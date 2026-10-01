"""End-to-end qua HTTP: mỗi request một mẫu, response giữ nguyên như provider trả về."""

import json
import logging

from tests.fakes import OPENROUTER_KEY
from tests.fixtures import P1_CSV_ROW, P1_INPUT, p1_request, p2_request

P1_URL = "/api/v1/condition-relation/decide"
P2_URL = "/api/v1/performer-lane/decide"


def _keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from _keys(v)


def test_p1_laya_returns_provider_response_verbatim(client, fake_laya):
    response = client.post(P1_URL, json=p1_request("laya"))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"model", "answers", "usage", "routing"}  # đúng các khóa Laya trả
    assert body["answers"]["relation"]["type"] == "choice"
    assert body["answers"]["relation"]["choice"] == "and"
    assert response.headers["X-Service-Platform"] == "laya"
    assert response.headers["X-Strategy"] == "jev_native"
    assert response.headers["X-Request-ID"].startswith("req_")


def test_p1_openrouter_keeps_provider_fields_and_recombines_answers(client, fake_respan):
    response = client.post(P1_URL, json=p1_request("openrouter"))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"model", "answers", "usage", "provider"}  # đúng các khóa Respan trả
    assert body["model"] == "respan/span-01-lite-20260925"
    assert list(body["answers"]) == ["relation"]
    assert body["answers"]["relation"]["choice"] == "and"
    assert response.headers["X-Strategy"] == "noul_decomposition"
    assert list(fake_respan.requests[0]["questions"]) == ["relation__0", "relation__1", "relation__2"]


def test_p2_openrouter_single_request(client, fake_respan):
    body = client.post(P2_URL, json=p2_request("openrouter")).json()
    assert set(body["answers"]) == {"performer", "evidence", "mixed_lanes"}
    assert body["answers"]["performer"]["choice"] == "pmkt_frontend"
    assert body["answers"]["mixed_lanes"] == {"type": "noul", "noul": 0.1}  # noul gốc trả nguyên văn
    assert len(fake_respan.requests) == 1


def test_full_csv_row_accepted_and_labels_never_reach_provider(client, fake_laya):
    response = client.post(P1_URL, json={"service_platform": "laya", **P1_CSV_ROW, "options": {"x": 1}})
    assert response.status_code == 200
    sent = fake_laya.requests[0]
    assert not {"sample_id", "expected_relation", "pair_scope", "label_status", "options"}.intersection(_keys(sent))
    assert "CR-001" not in json.dumps(sent, ensure_ascii=False)


def test_input_json_as_csv_string(client):
    response = client.post(P1_URL, json=p1_request("laya", json.dumps(P1_INPUT, ensure_ascii=False)))
    assert response.status_code == 200


def test_provider_rejection_passes_provider_error_through(client, fake_respan):
    fake_respan.status_sequence = [400]
    response = client.post(P1_URL, json=p1_request("openrouter"))
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "PROVIDER_REJECTED_REQUEST"
    assert error["provider_status"] == 400
    assert error["provider_error"] == {"error": {"message": "simulated 400", "code": 400}}


def test_rate_limit_is_retried(client, fake_respan, sleeps):
    fake_respan.status_sequence = [429, 200]
    assert client.post(P1_URL, json=p1_request("openrouter")).status_code == 200
    assert len(sleeps) == 1


def test_auth_failure_is_502(client, fake_respan):
    fake_respan.api_key = "another-key"
    response = client.post(P1_URL, json=p1_request("openrouter"))
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_AUTH_FAILED"


def test_request_errors(client):
    assert client.post(P1_URL, json=p1_request("nope")).status_code == 400
    assert client.post(P1_URL, json=p1_request("typesafe")).status_code == 503
    assert client.post(P1_URL, json=p1_request("laya", "{broken")).json()["error"]["code"] == "INVALID_INPUT_JSON"
    missing = client.post(P1_URL, json=p1_request("laya", {**P1_INPUT, "clause_text": ""}))
    assert (missing.status_code, missing.json()["error"]["code"]) == (422, "MISSING_INPUT_FIELD")
    no_input = client.post(P1_URL, json={"service_platform": "laya"})
    assert (no_input.status_code, no_input.json()["error"]["code"]) == (422, "VALIDATION_ERROR")


def test_providers_endpoint_masks_key_and_logs_never_contain_it(client, caplog):
    caplog.set_level(logging.INFO, logger="decision_pipeline")
    providers = client.get("/api/v1/providers").json()
    openrouter = next(p for p in providers if p["name"] == "openrouter")
    assert openrouter["api_key"] and OPENROUTER_KEY not in openrouter["api_key"]
    client.post(P1_URL, json=p1_request("openrouter"))
    assert OPENROUTER_KEY not in json.dumps(providers)
    assert OPENROUTER_KEY not in caplog.text


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "enabled_providers": ["laya", "openrouter"]}
