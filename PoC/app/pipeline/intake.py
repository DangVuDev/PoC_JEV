"""CHẶNG 1 — Tiếp nhận (BA mục 3). Không gọi mạng."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from ..config import ProviderConfig
from ..errors import ErrorCode, PipelineError
from ..observability import log_event
from ..schemas.internal import IntakeRecord
from ..schemas.request import DecideRequest
from .executor.registry import ProviderRegistry
from .tasks import TaskDefinition


@dataclass
class IntakeResult:
    provider: ProviderConfig
    model: str
    record: IntakeRecord


def run_intake(task: TaskDefinition, request: DecideRequest, registry: ProviderRegistry) -> IntakeResult:
    # 1.1 provider hợp lệ và đã cấu hình; model lấy từ .env.
    provider = registry.resolve(request.service_platform)
    if not provider.default_model:
        raise PipelineError(
            ErrorCode.PROVIDER_NOT_CONFIGURED,
            f"provider '{provider.name}' chưa có DEFAULT_MODEL trong .env",
        )

    # 1.2 parse input_json: nhận object hoặc chuỗi JSON (như trong CSV).
    raw_input = request.input_json
    if isinstance(raw_input, str):
        try:
            raw_input = json.loads(raw_input)
        except json.JSONDecodeError as exc:
            raise PipelineError(ErrorCode.INVALID_INPUT_JSON, f"input_json không phải JSON hợp lệ: {exc.msg}") from exc
    if not isinstance(raw_input, dict):
        raise PipelineError(ErrorCode.INVALID_INPUT_JSON, "input_json phải là một object")

    # 1.3 chỉ giữ trường đầu vào đã khai báo; khóa lạ trong input_json không được đi tiếp.
    data = {k: raw_input[k] for k in task.input_fields if k in raw_input}

    # 1.4 trường bắt buộc theo bài toán.
    error = task.validate_input(data)
    if error:
        raise error

    record = IntakeRecord(request_id="req_" + uuid.uuid4().hex[:16], task=task.name, input=data)
    log_event("intake.accepted", request_id=record.request_id, task=task.name, provider=provider.name, model=provider.default_model)
    return IntakeResult(provider=provider, model=provider.default_model, record=record)
