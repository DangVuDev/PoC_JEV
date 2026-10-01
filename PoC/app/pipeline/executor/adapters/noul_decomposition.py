"""Chiến lược B — phân rã: provider chỉ nhận noul (OpenRouter/Respan, BA mục 5.4).

Một câu choice K lựa chọn (hoặc score K mức) được tách thành K câu noul độc lập,
đặt trong cùng một request. qid con luôn dùng chỉ số (`<qid>__<i>`) để an toàn với
mọi ký tự trong option id; ánh xạ ngược nằm trong DecompositionPlan.
"""

from __future__ import annotations

from typing import Any

from ....schemas.internal import CanonicalDecisionRequest, DecompositionPlan, Question
from ...questions import noul_question
from .base import ProviderAdapter


class NoulDecompositionAdapter(ProviderAdapter):
    strategy = "noul_decomposition"

    def translate_questions(
        self, request: CanonicalDecisionRequest
    ) -> tuple[dict[str, dict[str, Any]], DecompositionPlan]:
        wire: dict[str, dict[str, Any]] = {}
        plan: DecompositionPlan = {}
        for qid, question in request.questions.items():
            if question.type == "noul":
                wire[qid] = question.to_wire()
                continue
            mapping: dict[str, Any] = {}
            for index, (option, label) in enumerate(_options(question)):
                sub_qid = f"{qid}__{index}"
                wire[sub_qid] = noul_question(
                    f"{question.instructions}\nPhương án đang xét: {label}\nPhương án này có phải là đáp án đúng không?",
                    f"đúng, đáp án là {label}",
                    f"sai, đáp án không phải {label}",
                ).to_wire()
                mapping[sub_qid] = option
            plan[qid] = mapping
        return wire, plan


def _options(question: Question) -> list[tuple[Any, str]]:
    if question.type == "choice":
        return [(key, f"{key}: {desc}" if desc else key) for key, desc in question.criteria.items()]
    return [(level, f"mức {level}: {desc}") for level, desc in enumerate(question.criteria)]
