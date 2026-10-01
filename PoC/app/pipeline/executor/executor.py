"""RequestExecutor: điều phối chặng 3 cho một mẫu (BA mục 5)."""

from __future__ import annotations

from typing import Mapping

from ...config import ProviderConfig
from ...errors import ErrorCode, PipelineError
from ...observability import log_event
from ...schemas.internal import CanonicalDecisionRequest, ExecutionResult
from ..tasks import FORBIDDEN_PAYLOAD_KEYS
from .adapters import ADAPTERS, ProviderAdapter
from .guards import assert_no_label_leak
from .transport import HttpTransport


class RequestExecutor:
    def __init__(self, transport: HttpTransport, adapters: Mapping[str, ProviderAdapter] | None = None):
        self._transport = transport
        self._adapters = dict(adapters or ADAPTERS)

    def adapter_for(self, config: ProviderConfig) -> ProviderAdapter:
        adapter = self._adapters.get(config.adapter)
        if adapter is None:
            raise PipelineError(ErrorCode.PROVIDER_NOT_CONFIGURED, f"không có adapter '{config.adapter}'")
        return adapter

    def execute(
        self, request: CanonicalDecisionRequest, request_id: str, config: ProviderConfig, model: str
    ) -> ExecutionResult:
        adapter = self.adapter_for(config)
        payloads = adapter.build_payloads(request, config, model)
        for payload in payloads:
            assert_no_label_leak(payload.body, FORBIDDEN_PAYLOAD_KEYS)

        raws = []
        plan: dict[str, dict] = {}
        latency_ms = 0.0
        for payload in payloads:
            call = self._transport.send(config, payload.body)
            raws.append(call.raw)
            latency_ms += call.latency_ms
            for orig, mapping in payload.plan.items():
                plan.setdefault(orig, {}).update(mapping)

        log_event(
            "execute.done",
            request_id=request_id,
            provider=config.name,
            strategy=adapter.strategy,
            payloads=len(payloads),
            questions=sum(len(p.body["questions"]) for p in payloads),
            latency_ms=round(latency_ms, 1),
        )
        return ExecutionResult(strategy=adapter.strategy, raw_responses=raws, plan=plan, latency_ms=latency_ms)
