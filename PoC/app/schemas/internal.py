"""Mô hình dữ liệu nội bộ chạy giữa các chặng (BA mục 6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Task = Literal["p1", "p2"]
QuestionType = Literal["choice", "score", "noul"]


@dataclass(frozen=True)
class Question:
    """Một câu hỏi theo chuẩn Jev.

    criteria: choice -> {option_id: mô tả}; score -> [mô tả mức 0, mức 1, ...];
    noul -> {"true": mô tả, "false": mô tả}.
    """

    type: QuestionType
    instructions: str
    criteria: dict[str, str] | list[str]

    def to_wire(self) -> dict[str, Any]:
        criteria = dict(self.criteria) if isinstance(self.criteria, dict) else list(self.criteria)
        return {"type": self.type, "instructions": self.instructions, "criteria": criteria}


@dataclass
class IntakeRecord:
    """Đầu ra chặng 1. `input` chỉ chứa trường được phép gửi tới provider."""

    request_id: str
    task: Task
    input: dict[str, Any]


@dataclass
class CanonicalDecisionRequest:
    """Đầu ra chặng 2: request chuẩn Jev, không phụ thuộc nhà cung cấp."""

    task: Task
    prompt_version: str
    state_text: str
    state_structured: dict[str, Any] | None
    questions: dict[str, Question]
    answer_space: dict[str, list[Any]]


# orig_qid -> {sub_qid: giá trị lựa chọn gốc}
DecompositionPlan = dict[str, dict[str, Any]]


@dataclass
class ProviderPayload:
    body: dict[str, Any]
    plan: DecompositionPlan = field(default_factory=dict)


@dataclass
class ProviderCallResult:
    raw: dict[str, Any]
    latency_ms: float
    attempts: int


@dataclass
class ExecutionResult:
    """Đầu ra chặng 3: các response thô của provider cho một mẫu."""

    strategy: str
    raw_responses: list[dict[str, Any]]
    plan: DecompositionPlan
    latency_ms: float
