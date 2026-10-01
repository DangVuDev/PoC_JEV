from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pipeline.executor.transport import HttpTransport

from tests.fakes import LAYA_HOST, OPENROUTER_HOST, OPENROUTER_KEY, FakeLaya, FakeRespan, router

BASE_ENV = {
    "DECISION_ENABLED_PROVIDERS": "laya,openrouter",
    "DECISION_LAYA_ENDPOINT": f"http://{LAYA_HOST}/v1/systemone",
    "DECISION_OPENROUTER_ENDPOINT": f"https://{OPENROUTER_HOST}/api/alpha/decisions",
    "DECISION_OPENROUTER_API_KEY": OPENROUTER_KEY,
    "DECISION_OPENROUTER_MIN_INTERVAL_S": "0",
    "DECISION_OPENROUTER_MAX_RETRIES": "3",
}


def make_settings(**overrides: str) -> Settings:
    return Settings.from_env({**BASE_ENV, **overrides})


@pytest.fixture
def fake_laya() -> FakeLaya:
    return FakeLaya()


@pytest.fixture
def fake_respan() -> FakeRespan:
    return FakeRespan()


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def transport(fake_laya, fake_respan, sleeps) -> HttpTransport:
    return HttpTransport(client=httpx.Client(transport=router(fake_laya, fake_respan)), sleep=sleeps.append)


@pytest.fixture
def client(transport) -> TestClient:
    with TestClient(create_app(make_settings(), transport)) as test_client:
        yield test_client
