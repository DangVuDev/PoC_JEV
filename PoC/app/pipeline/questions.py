"""Primitive dựng câu hỏi chuẩn Jev: choice / score / noul.

Dùng chung cho chặng 2 (dựng câu hỏi nghiệp vụ) và chặng 3 (phân rã câu hỏi cho
provider thiếu năng lực). Định dạng criteria của noul là {"true", "false"}, đã
xác minh ở cả Laya (laya/common.py) lẫn OpenRouter/Respan (lỗi 400 thật).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..schemas.internal import Question


def choice_question(instructions: str, options: Mapping[str, str]) -> Question:
    _require_text(instructions, "instructions")
    if len(options) < 2:
        raise ValueError("câu choice cần ít nhất 2 lựa chọn")
    for key, desc in options.items():
        _require_text(key, "option id")
        if not isinstance(desc, str):
            raise ValueError(f"mô tả của lựa chọn '{key}' phải là chuỗi")
    return Question(type="choice", instructions=instructions, criteria=dict(options))


def score_question(instructions: str, levels: Sequence[str]) -> Question:
    _require_text(instructions, "instructions")
    if len(levels) < 2:
        raise ValueError("câu score cần ít nhất 2 mức")
    for i, desc in enumerate(levels):
        _require_text(desc, f"mô tả mức {i}")
    return Question(type="score", instructions=instructions, criteria=list(levels))


def noul_question(instructions: str, true_desc: str, false_desc: str) -> Question:
    _require_text(instructions, "instructions")
    _require_text(true_desc, "mô tả true")
    _require_text(false_desc, "mô tả false")
    return Question(type="noul", instructions=instructions, criteria={"true": true_desc, "false": false_desc})


def answer_space_of(question: Question) -> list[Any]:
    """Tập giá trị hợp lệ của câu trả lời, theo thứ tự ưu tiên khi phá hòa."""
    if question.type == "choice":
        return list(question.criteria)
    if question.type == "score":
        return list(range(len(question.criteria)))
    return [True, False]


def _require_text(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} phải là chuỗi không rỗng")
