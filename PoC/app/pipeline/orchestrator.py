"""Nối 4 chặng cho một mẫu: Intake -> Normalizer -> Executor -> Response builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ErrorCode, PipelineError
from ..schemas.request import DecideRequest
from .executor.executor import RequestExecutor
from .executor.registry import ProviderRegistry
from .intake import run_intake
from .response.builder import build_response
from .tasks import get_task


@dataclass
class PipelineOutput:
    body: dict[str, Any]
    request_id: str
    provider: str
    strategy: str
    latency_ms: float


class DecisionPipeline:
    def __init__(self, registry: ProviderRegistry, executor: RequestExecutor):
        self._registry = registry
        self._executor = executor

    def run(self, task_name: str, request: DecideRequest) -> PipelineOutput:
        task = get_task(task_name)
        intake = run_intake(task, request, self._registry)  # chặng 1

        try:
            canonical = task.normalize(intake.record)  # chặng 2
        except (ValueError, KeyError) as exc:
            raise PipelineError(ErrorCode.MISSING_INPUT_FIELD, f"không chuẩn hóa được input_json: {exc}") from exc

        execution = self._executor.execute(canonical, intake.record.request_id, intake.provider, intake.model)  # chặng 3
        body = build_response(canonical, execution)  # chặng 4
        return PipelineOutput(
            body=body,
            request_id=intake.record.request_id,
            provider=intake.provider.name,
            strategy=execution.strategy,
            latency_ms=execution.latency_ms,
        )
