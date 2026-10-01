from dataclasses import replace

import httpx
import pytest

from app.errors import ErrorCode, PipelineError
from app.pipeline.executor.transport import HttpTransport, RateLimiter
from tests.conftest import make_settings
from tests.fakes import OPENROUTER_KEY

CONFIG = replace(make_settings().providers["openrouter"], min_interval_s=0, max_retries=3)
OK_BODY = {"answers": {"q": {"type": "noul", "noul": 0.7}}}


def _transport(responses, sleeps):
    calls = []

    def handle(request):
        calls.append(request)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return HttpTransport(client=httpx.Client(transport=httpx.MockTransport(handle)), sleep=sleeps.append), calls


def test_success_sends_bearer_auth():
    transport, calls = _transport([httpx.Response(200, json=OK_BODY)], [])
    result = transport.send(CONFIG, {"state": "x", "questions": {}})
    assert result.raw == OK_BODY and result.attempts == 1
    assert calls[0].headers["Authorization"] == f"Bearer {OPENROUTER_KEY}"


def test_429_is_retried_then_succeeds():
    sleeps = []
    transport, calls = _transport([httpx.Response(429), httpx.Response(429), httpx.Response(200, json=OK_BODY)], sleeps)
    assert transport.send(CONFIG, {}).attempts == 3
    assert len(calls) == 3 and len(sleeps) == 2


def test_retry_after_header_is_respected():
    sleeps = []
    transport, _ = _transport([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json=OK_BODY)], sleeps)
    transport.send(CONFIG, {})
    assert sleeps == [7.0]


def test_timeouts_exhaust_retries():
    sleeps = []
    transport, calls = _transport([httpx.ReadTimeout("t")] * 4, sleeps)
    with pytest.raises(PipelineError) as exc:
        transport.send(CONFIG, {})
    assert exc.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert len(calls) == 4 and len(sleeps) == 3  # không ngủ sau lần thử cuối


def test_400_is_not_retried_and_provider_error_is_passed_through():
    provider_error = {"error": {"message": "Respan only accepts noul questions", "code": 400}}
    transport, calls = _transport([httpx.Response(400, json=provider_error)], [])
    with pytest.raises(PipelineError) as exc:
        transport.send(CONFIG, {})
    assert exc.value.code == ErrorCode.PROVIDER_REJECTED_REQUEST
    assert exc.value.details == {"provider_status": 400, "provider_error": provider_error}
    assert len(calls) == 1


def test_echoed_api_key_is_masked_in_provider_error():
    transport, _ = _transport([httpx.Response(400, json={"error": {"message": f"bad key {OPENROUTER_KEY}"}})], [])
    with pytest.raises(PipelineError) as exc:
        transport.send(CONFIG, {})
    assert OPENROUTER_KEY not in str(exc.value.details)


def test_401_is_auth_error():
    transport, _ = _transport([httpx.Response(401, json={"error": {"message": "Missing Authentication header"}})], [])
    with pytest.raises(PipelineError) as exc:
        transport.send(CONFIG, {})
    assert (exc.value.code, exc.value.http_status) == (ErrorCode.PROVIDER_AUTH_FAILED, 502)


@pytest.mark.parametrize("response", [httpx.Response(200, text="not json"), httpx.Response(200, json={"no": "answers"})])
def test_invalid_response_body(response):
    transport, _ = _transport([response], [])
    with pytest.raises(PipelineError) as exc:
        transport.send(CONFIG, {})
    assert exc.value.code == ErrorCode.PROVIDER_INVALID_RESPONSE


def test_rate_limiter_spaces_calls_per_provider():
    now = [100.0]
    sleeps = []
    limiter = RateLimiter(clock=lambda: now[0], sleep=sleeps.append)
    limiter.acquire("openrouter", 1.0)
    limiter.acquire("openrouter", 1.0)
    limiter.acquire("openrouter", 1.0)
    limiter.acquire("laya", 1.0)  # provider khác không phải chờ
    assert sleeps == [1.0, 2.0]
