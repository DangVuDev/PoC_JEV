"""Gọi provider THẬT theo cấu hình trong PoC/.env.

Chạy: DECISION_LIVE_TESTS=1 pytest tests/integration
Provider nào chưa bật trong .env sẽ tự bỏ qua.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from tests.fixtures import p1_request, p2_request

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("DECISION_LIVE_TESTS") != "1", reason="đặt DECISION_LIVE_TESTS=1 để gọi provider thật"),
]
PROVIDERS = ["laya", "openrouter", "typesafe", "vercelgateway"]


@pytest.fixture(scope="module")
def live():
    settings = load_settings()
    with TestClient(create_app(settings)) as client:
        yield client, settings


@pytest.mark.parametrize("provider", PROVIDERS)
def test_live_p1(live, provider):
    client, settings = live
    if not settings.providers[provider].enabled:
        pytest.skip(settings.providers[provider].disabled_reason)
    response = client.post("/api/v1/condition-relation/decide", json=p1_request(provider))
    assert response.status_code == 200, response.text
    assert response.json()["answers"]["relation"]["choice"] in ("and", "or", "insufficient_evidence")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_live_p2(live, provider):
    client, settings = live
    if not settings.providers[provider].enabled:
        pytest.skip(settings.providers[provider].disabled_reason)
    response = client.post("/api/v1/performer-lane/decide", json=p2_request(provider))
    assert response.status_code == 200, response.text
    assert set(response.json()["answers"]) >= {"performer", "evidence", "mixed_lanes"}
