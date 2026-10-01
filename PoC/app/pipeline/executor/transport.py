"""Transport HTTP: xác thực, timeout, retry/backoff, giới hạn tốc độ (BA mục 5.5)."""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

import httpx

from ...config import ProviderConfig
from ...errors import ErrorCode, PipelineError
from ...observability import log_event
from ...schemas.internal import ProviderCallResult

MAX_BACKOFF_S = 30.0
MAX_RETRY_AFTER_S = 60.0
ERROR_DETAIL_LIMIT = 300


class RateLimiter:
    """Giữ khoảng cách tối thiểu giữa 2 request tới cùng một provider, an toàn đa luồng.

    Mỗi lượt gọi đặt trước một khe thời gian, rồi ngủ bên ngoài lock, nên nhiều luồng
    xếp hàng đúng thứ tự mà không giữ lock trong lúc chờ.
    """

    def __init__(self, clock: Callable[[], float], sleep: Callable[[float], None]):
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_slot: dict[str, float] = {}

    def acquire(self, key: str, min_interval_s: float) -> None:
        if min_interval_s <= 0:
            return
        with self._lock:
            now = self._clock()
            start = max(now, self._next_slot.get(key, now))
            self._next_slot[key] = start + min_interval_s
            wait = start - now
        if wait > 0:
            self._sleep(wait)


class HttpTransport:
    def __init__(
        self,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = client or httpx.Client()
        self._sleep = sleep
        self._clock = clock
        self._limiter = RateLimiter(clock, sleep)

    def close(self) -> None:
        self._client.close()

    def send(self, config: ProviderConfig, body: dict[str, Any]) -> ProviderCallResult:
        headers = {"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        last_problem = "không rõ nguyên nhân"
        last_details: dict[str, Any] | None = None
        total_attempts = config.max_retries + 1
        for attempt in range(total_attempts):
            is_last = attempt == total_attempts - 1
            self._limiter.acquire(config.name, config.min_interval_s)
            started = self._clock()
            try:
                response = self._client.post(config.endpoint, json=body, headers=headers, timeout=config.timeout_s)
            except httpx.TimeoutException:
                last_problem = f"timeout sau {config.timeout_s}s"
                self._log(config, attempt, None, started)
                if not is_last:
                    self._sleep(self._backoff(config, attempt))
                continue
            except httpx.TransportError as exc:
                last_problem = f"lỗi kết nối ({type(exc).__name__})"
                self._log(config, attempt, None, started)
                if not is_last:
                    self._sleep(self._backoff(config, attempt))
                continue

            latency_ms = (self._clock() - started) * 1000.0
            status = response.status_code
            self._log(config, attempt, status, started)

            if status == 200:
                return ProviderCallResult(raw=self._parse(response, config), latency_ms=latency_ms, attempts=attempt + 1)

            provider_error = self._error_body(response, config)
            if status == 429 or status >= 500:
                last_problem = f"HTTP {status}"
                last_details = {"provider_status": status, "provider_error": provider_error}
                if not is_last:
                    self._sleep(self._retry_after(response) or self._backoff(config, attempt))
                continue
            details = {"provider_status": status, "provider_error": provider_error}
            if status in (401, 403):
                raise PipelineError(
                    ErrorCode.PROVIDER_AUTH_FAILED, f"provider '{config.name}' từ chối xác thực", details=details
                )
            # 400/422/...: lỗi thiết kế payload, retry cũng không có tác dụng.
            raise PipelineError(
                ErrorCode.PROVIDER_REJECTED_REQUEST, f"provider '{config.name}' từ chối request", details=details
            )

        raise PipelineError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            f"provider '{config.name}' không phản hồi thành công sau {total_attempts} lần thử: {last_problem}",
            details=last_details,
        )

    @staticmethod
    def _backoff(config: ProviderConfig, attempt: int) -> float:
        base = max(config.min_interval_s, 0.5)
        return min(base * (2**attempt), MAX_BACKOFF_S)

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return min(max(float(raw), 0.0), MAX_RETRY_AFTER_S)
        except ValueError:
            return None

    @staticmethod
    def _parse(response: httpx.Response, config: ProviderConfig) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise PipelineError(
                ErrorCode.PROVIDER_INVALID_RESPONSE, f"provider '{config.name}' trả response không phải JSON"
            ) from exc
        if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
            raise PipelineError(
                ErrorCode.PROVIDER_INVALID_RESPONSE, f"provider '{config.name}' trả response thiếu 'answers'"
            )
        return body

    @staticmethod
    def _error_body(response: httpx.Response, config: ProviderConfig) -> Any:
        """Lỗi nguyên văn của provider để trả lại client; chỉ che API key nếu bị phản hồi lại."""
        text = response.text
        if config.api_key:
            text = text.replace(config.api_key, config.api_key_masked)
        try:
            return json.loads(text)
        except ValueError:
            return text[:ERROR_DETAIL_LIMIT]

    def _log(self, config: ProviderConfig, attempt: int, status: int | None, started: float) -> None:
        log_event(
            "execute.http_call",
            provider=config.name,
            attempt=attempt + 1,
            status=status,
            latency_ms=round((self._clock() - started) * 1000.0, 1),
        )
