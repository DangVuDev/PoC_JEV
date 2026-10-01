import pytest

from app.errors import ErrorCode, PipelineError
from app.pipeline.normalizer import p1_condition_relation
from app.pipeline.questions import score_question
from app.pipeline.response.builder import build_response
from app.pipeline.response.recombine import recombine_answers
from app.schemas.internal import ExecutionResult, IntakeRecord

P1_PLAN = {"relation": {"relation__0": "and", "relation__1": "or", "relation__2": "insufficient_evidence"}}


def _canonical():
    record = IntakeRecord("r", "p1", {"clause_text": "A và B", "left_condition": "A", "right_condition": "B"})
    return p1_condition_relation.normalize(record)


def _nouls(values):
    return {qid: {"type": "noul", "noul": v} for qid, v in values.items()}


def test_native_single_response_is_returned_verbatim():
    raw = {"model": "laya-rl-agent", "answers": {"relation": {"type": "choice", "choice": "or"}},
           "usage": {"input_tokens": 119, "output_tokens": 0}, "routing": {"model": "multilingual"}}
    body = build_response(_canonical(), ExecutionResult("jev_native", [raw], {}, 10.0))
    assert body == raw


def test_decomposed_answers_recombined_other_fields_kept():
    # Response thật của Respan cho CR-001 (2026-09-30).
    raw = {"model": "respan/span-01-lite-20260925",
           "answers": _nouls({"relation__0": 0.5107249, "relation__1": 0.039283, "relation__2": 0.1652176}),
           "usage": {"input_tokens": 373, "output_tokens": 0, "cost": 0},
           "id": "gen-dec-1", "provider": "Respan"}
    body = build_response(_canonical(), ExecutionResult("noul_decomposition", [raw], P1_PLAN, 10.0))
    assert body["answers"] == {"relation": {
        "type": "choice", "choice": "and",
        "probabilities": {"and": 0.5107249, "or": 0.039283, "insufficient_evidence": 0.1652176},
    }}
    assert {k: body[k] for k in ("model", "usage", "id", "provider")} == {k: raw[k] for k in ("model", "usage", "id", "provider")}


def test_tie_resolved_by_declared_option_order():
    answers = recombine_answers(_canonical(), _nouls({"relation__0": 0.4, "relation__1": 0.4, "relation__2": 0.1}), P1_PLAN)
    assert answers["relation"]["choice"] == "and"


def test_score_recombined_as_score_answer():
    canonical = _canonical()
    canonical.questions = {"level": score_question("Mức?", ["thấp", "vừa", "cao"])}
    canonical.answer_space = {"level": [0, 1, 2]}
    plan = {"level": {"level__0": 0, "level__1": 1, "level__2": 2}}
    answers = recombine_answers(canonical, _nouls({"level__0": 0.1, "level__1": 0.2, "level__2": 0.9}), plan)
    assert answers["level"] == {"type": "score", "score": 2, "probabilities": {"0": 0.1, "1": 0.2, "2": 0.9}}


@pytest.mark.parametrize("sub_answers", [
    _nouls({"relation__0": 0.5, "relation__1": 0.2}),
    _nouls({"relation__0": 0.5, "relation__1": 0.2, "relation__2": 1.7}),
    {**_nouls({"relation__0": 0.5, "relation__1": 0.2}), "relation__2": {"type": "noul"}},
])
def test_incomplete_decomposition(sub_answers):
    with pytest.raises(PipelineError) as exc:
        recombine_answers(_canonical(), sub_answers, P1_PLAN)
    assert exc.value.code == ErrorCode.INCOMPLETE_DECOMPOSITION


def test_multiple_payloads_merge_answers_and_sum_usage():
    first = {"model": "m", "answers": _nouls({"relation__0": 0.7, "relation__1": 0.1}), "usage": {"input_tokens": 100, "output_tokens": 0, "cost": 0}}
    second = {"model": "m", "answers": _nouls({"relation__2": 0.2}), "usage": {"input_tokens": 50, "output_tokens": 0, "cost": 0}}
    body = build_response(_canonical(), ExecutionResult("noul_decomposition", [first, second], P1_PLAN, 10.0))
    assert body["answers"]["relation"]["choice"] == "and"
    assert body["usage"] == {"input_tokens": 150, "output_tokens": 0, "cost": 0}
