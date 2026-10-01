"""Normalizer P2 Performer Lane.

performer: choice động theo members của chính mẫu + insufficient_evidence.
evidence: choice cố định {object, verb, context}.
mixed_lanes: noul.
"""

from __future__ import annotations

from typing import Any

from ...errors import ErrorCode, PipelineError
from ...schemas.internal import CanonicalDecisionRequest, IntakeRecord
from ..questions import answer_space_of, choice_question, noul_question
from .prompts import P2_VERSION, get_prompt

INPUT_FIELDS = ("row_text", "subject", "substeps", "members", "hints")
INSUFFICIENT = "insufficient_evidence"


def validate_input(data: dict[str, Any]) -> PipelineError | None:
    row_text = data.get("row_text")
    if not isinstance(row_text, str) or not row_text.strip():
        return PipelineError(ErrorCode.MISSING_INPUT_FIELD, "thiếu hoặc rỗng trường: row_text")

    members = data.get("members")
    if not isinstance(members, list) or not members:
        return PipelineError(ErrorCode.MISSING_INPUT_FIELD, "members phải là danh sách có ít nhất 1 phần tử")
    seen: set[str] = set()
    for i, member in enumerate(members):
        member_id = member.get("id") if isinstance(member, dict) else None
        if not isinstance(member_id, str) or not member_id.strip():
            return PipelineError(ErrorCode.MISSING_INPUT_FIELD, f"members[{i}] thiếu id")
        if member_id == INSUFFICIENT:
            return PipelineError(ErrorCode.MISSING_INPUT_FIELD, f"members[{i}].id trùng giá trị dành riêng '{INSUFFICIENT}'")
        if member_id in seen:
            return PipelineError(ErrorCode.MISSING_INPUT_FIELD, f"members có id trùng: {member_id}")
        seen.add(member_id)
    return None


def _member_description(member: dict[str, Any]) -> str:
    parts = [member.get("name"), member.get("tier"), member.get("description")]
    return " — ".join(p.strip() for p in parts if isinstance(p, str) and p.strip()) or member["id"]


def _state_text(data: dict[str, Any], prompt: dict) -> str:
    lines = [prompt["state_row"].format(row_text=data["row_text"].strip())]
    subject = data.get("subject")
    if isinstance(subject, dict) and isinstance(subject.get("text"), str) and subject["text"].strip():
        lines.append(prompt["state_subject"].format(subject=subject["text"].strip()))
    quotes = [
        s["quote"].strip()
        for s in data.get("substeps") or []
        if isinstance(s, dict) and isinstance(s.get("quote"), str) and s["quote"].strip()
    ]
    if quotes:
        lines.append(prompt["state_substeps"].format(quotes="; ".join(quotes)))
    return "\n".join(lines)


def normalize(record: IntakeRecord, version: str = P2_VERSION) -> CanonicalDecisionRequest:
    prompt = get_prompt(version)
    data = record.input

    performer_options = {m["id"]: _member_description(m) for m in data["members"]}
    performer_options[INSUFFICIENT] = prompt["performer"]["insufficient_evidence"]
    questions = {
        "performer": choice_question(prompt["performer"]["instructions"], performer_options),
        "evidence": choice_question(prompt["evidence"]["instructions"], prompt["evidence"]["options"]),
        "mixed_lanes": noul_question(
            prompt["mixed_lanes"]["instructions"], prompt["mixed_lanes"]["true"], prompt["mixed_lanes"]["false"]
        ),
    }
    structured = {k: data[k] for k in ("row_text", "subject", "substeps") if k in data}
    return CanonicalDecisionRequest(
        task="p2",
        prompt_version=version,
        state_text=_state_text(data, prompt),
        state_structured=structured,
        questions=questions,
        answer_space={qid: answer_space_of(q) for qid, q in questions.items()},
    )
