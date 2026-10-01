"""4a — Gộp các câu noul đã phân rã về câu hỏi gốc, theo đúng định dạng answer của Jev (BA mục 6.1).

Chỉ chạy khi adapter đã phân rã (chiến lược noul_decomposition). Kết quả có dạng giống
hệt provider hỗ trợ choice/score trả về, để client đọc một kiểu duy nhất:
    choice -> {"type": "choice", "choice": <option>, "probabilities": {option: noul}}
    score  -> {"type": "score",  "score": <level>,  "probabilities": {"0": noul, ...}}
Probabilities ở đây là xác suất độc lập của từng câu noul, tổng không nhất thiết bằng 1.
"""

from __future__ import annotations

from typing import Any

from ...errors import ErrorCode, PipelineError
from ...schemas.internal import CanonicalDecisionRequest, DecompositionPlan


def recombine_answers(
    request: CanonicalDecisionRequest, raw_answers: dict[str, Any], plan: DecompositionPlan
) -> dict[str, Any]:
    sub_qids = {sub for mapping in plan.values() for sub in mapping}
    answers: dict[str, Any] = {}
    for qid, question in request.questions.items():
        if qid not in plan:
            if qid in raw_answers:
                answers[qid] = raw_answers[qid]
            continue
        scores = {option: _noul(raw_answers.get(sub), sub) for sub, option in plan[qid].items()}
        # Hòa điểm: ưu tiên theo thứ tự lựa chọn đã khai báo, để kết quả tất định.
        winner = max(request.answer_space[qid], key=lambda option: scores[option])
        probabilities = {str(option): scores[option] for option in request.answer_space[qid]}
        key = "choice" if question.type == "choice" else "score"
        answers[qid] = {"type": question.type, key: winner, "probabilities": probabilities}
    # Giữ lại câu trả lời provider gửi thêm ngoài tập câu hỏi (nếu có), trừ các câu con đã gộp.
    for qid, answer in raw_answers.items():
        if qid not in answers and qid not in sub_qids:
            answers[qid] = answer
    return answers


def _noul(answer: Any, sub_qid: str) -> float:
    value = answer.get("noul") if isinstance(answer, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
        raise PipelineError(
            ErrorCode.INCOMPLETE_DECOMPOSITION, f"provider không trả giá trị noul hợp lệ cho câu con '{sub_qid}'"
        )
    return float(value)
