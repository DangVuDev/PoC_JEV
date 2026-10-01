"""4b — Dựng response trả client: giữ nguyên response của provider (BA mục 6.2).

- jev_native, 1 payload: trả nguyên văn.
- noul_decomposition: giữ mọi trường của provider, chỉ thay `answers` bằng bản đã gộp về câu gốc.
- Nhiều payload (câu hỏi vượt giới hạn provider): lấy response đầu làm khung,
  gộp `answers` và cộng các trường số trong `usage`.
"""

from __future__ import annotations

import copy
from typing import Any

from ...errors import ErrorCode, PipelineError
from ...schemas.internal import CanonicalDecisionRequest, ExecutionResult
from .recombine import recombine_answers


def build_response(request: CanonicalDecisionRequest, execution: ExecutionResult) -> dict[str, Any]:
    if not execution.raw_responses:
        raise PipelineError(ErrorCode.PROVIDER_INVALID_RESPONSE, "provider không trả response nào")
    if len(execution.raw_responses) == 1 and not execution.plan:
        return execution.raw_responses[0]

    body = copy.deepcopy(execution.raw_responses[0])
    merged_answers: dict[str, Any] = {}
    for raw in execution.raw_responses:
        merged_answers.update(raw["answers"])
    body["answers"] = recombine_answers(request, merged_answers, execution.plan) if execution.plan else merged_answers
    if len(execution.raw_responses) > 1:
        body["usage"] = _sum_usage(execution.raw_responses)
    return body


def _sum_usage(raws: list[dict[str, Any]]) -> dict[str, Any] | None:
    usages = [r["usage"] for r in raws if isinstance(r.get("usage"), dict)]
    if not usages:
        return None
    keys = dict.fromkeys(k for u in usages for k in u)
    total: dict[str, Any] = {}
    for key in keys:
        values = [u[key] for u in usages if isinstance(u.get(key), (int, float)) and not isinstance(u.get(key), bool)]
        total[key] = sum(values) if values else usages[0].get(key)
    return total
