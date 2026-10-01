"""Normalizer P1 Condition Relation: 1 câu choice {and, or, insufficient_evidence}."""

from __future__ import annotations

from typing import Any

from ...errors import ErrorCode, PipelineError
from ...schemas.internal import CanonicalDecisionRequest, IntakeRecord
from ..questions import answer_space_of, choice_question
from .prompts import P1_VERSION, get_prompt

INPUT_FIELDS = ("clause_text", "left_condition", "right_condition")


def validate_input(data: dict[str, Any]) -> PipelineError | None:
    missing = [f for f in INPUT_FIELDS if not isinstance(data.get(f), str) or not data[f].strip()]
    if missing:
        return PipelineError(ErrorCode.MISSING_INPUT_FIELD, f"thiếu hoặc rỗng trường: {', '.join(missing)}")
    return None


def normalize(record: IntakeRecord, version: str = P1_VERSION) -> CanonicalDecisionRequest:
    prompt = get_prompt(version)
    data = record.input
    state_text = prompt["state_template"].format(
        clause_text=data["clause_text"].strip(),
        left_condition=data["left_condition"].strip(),
        right_condition=data["right_condition"].strip(),
    )
    relation = choice_question(prompt["relation"]["instructions"], prompt["relation"]["options"])
    return CanonicalDecisionRequest(
        task="p1",
        prompt_version=version,
        state_text=state_text,
        state_structured={k: data[k] for k in INPUT_FIELDS},
        questions={"relation": relation},
        answer_space={"relation": answer_space_of(relation)},
    )
