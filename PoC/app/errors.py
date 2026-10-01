"""Danh mục lỗi của pipeline (BA mục 7). Mỗi mã lỗi gắn cố định một HTTP status."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNKNOWN_PROVIDER = "UNKNOWN_PROVIDER"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    INVALID_INPUT_JSON = "INVALID_INPUT_JSON"
    MISSING_INPUT_FIELD = "MISSING_INPUT_FIELD"
    LABEL_LEAK_BLOCKED = "LABEL_LEAK_BLOCKED"
    PROVIDER_REJECTED_REQUEST = "PROVIDER_REJECTED_REQUEST"
    PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"
    INCOMPLETE_DECOMPOSITION = "INCOMPLETE_DECOMPOSITION"


HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.UNKNOWN_PROVIDER: 400,
    ErrorCode.PROVIDER_NOT_CONFIGURED: 503,
    ErrorCode.INVALID_INPUT_JSON: 422,
    ErrorCode.MISSING_INPUT_FIELD: 422,
    ErrorCode.LABEL_LEAK_BLOCKED: 500,
    ErrorCode.PROVIDER_REJECTED_REQUEST: 502,
    ErrorCode.PROVIDER_AUTH_FAILED: 502,
    ErrorCode.PROVIDER_UNAVAILABLE: 503,
    ErrorCode.PROVIDER_INVALID_RESPONSE: 502,
    ErrorCode.INCOMPLETE_DECOMPOSITION: 502,
}


class PipelineError(Exception):
    def __init__(self, code: ErrorCode, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    @property
    def http_status(self) -> int:
        return HTTP_STATUS[self.code]

    def to_body(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.details:
            error.update(self.details)
        return {"error": error}
