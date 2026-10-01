"""Interface CapabilityAdapter: canonical request -> payload đúng năng lực provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ....config import ProviderConfig
from ....schemas.internal import CanonicalDecisionRequest, DecompositionPlan, ProviderPayload


class ProviderAdapter(ABC):
    strategy: ClassVar[str]

    @abstractmethod
    def translate_questions(
        self, request: CanonicalDecisionRequest
    ) -> tuple[dict[str, dict[str, Any]], DecompositionPlan]:
        """Trả về (câu hỏi dạng wire, kế hoạch phân rã). Kế hoạch rỗng nghĩa là gửi nguyên bản."""

    def build_payloads(self, request: CanonicalDecisionRequest, config: ProviderConfig, model: str) -> list[ProviderPayload]:
        wire_questions, plan = self.translate_questions(request)
        state = self._state(request, config)
        payloads = []
        for chunk in _chunk(wire_questions, config.max_questions):
            chunk_plan = {
                orig: {sub: option for sub, option in mapping.items() if sub in chunk}
                for orig, mapping in plan.items()
            }
            body = {"model": model, "state": state, "questions": chunk}
            payloads.append(ProviderPayload(body=body, plan={k: v for k, v in chunk_plan.items() if v}))
        return payloads

    @staticmethod
    def _state(request: CanonicalDecisionRequest, config: ProviderConfig) -> str | dict[str, Any]:
        if config.state_format == "object" and request.state_structured:
            return request.state_structured
        return request.state_text


def _chunk(questions: dict[str, dict[str, Any]], size: int) -> list[dict[str, dict[str, Any]]]:
    items = list(questions.items())
    return [dict(items[i : i + size]) for i in range(0, len(items), size)] or [{}]
