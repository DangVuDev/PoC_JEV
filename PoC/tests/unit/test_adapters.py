from dataclasses import replace

import pytest

from app.errors import ErrorCode, PipelineError
from app.pipeline.executor.adapters import JevNativeAdapter, NoulDecompositionAdapter
from app.pipeline.executor.guards import assert_no_label_leak
from app.pipeline.normalizer import p1_condition_relation, p2_performer_lane
from app.pipeline.questions import score_question
from app.pipeline.tasks import FORBIDDEN_PAYLOAD_KEYS
from app.schemas.internal import IntakeRecord
from tests.conftest import make_settings
from tests.fixtures import P2_INPUT

P1_INPUT = {"clause_text": "A và B.", "left_condition": "A", "right_condition": "B"}


def _canonical(task, data):
    module = p1_condition_relation if task == "p1" else p2_performer_lane
    return module.normalize(IntakeRecord(request_id="r", task=task, input=data))


def test_native_passes_questions_through():
    config = make_settings().providers["laya"]
    [payload] = JevNativeAdapter().build_payloads(_canonical("p1", P1_INPUT), config, "multilingual")
    assert payload.plan == {}
    assert payload.body["model"] == "multilingual"
    assert payload.body["questions"]["relation"]["type"] == "choice"
    assert isinstance(payload.body["state"], str)


def test_native_object_state_when_configured():
    config = replace(make_settings().providers["laya"], state_format="object")
    [payload] = JevNativeAdapter().build_payloads(_canonical("p1", P1_INPUT), config, "m")
    assert payload.body["state"] == P1_INPUT


def test_decomposition_turns_p1_choice_into_three_nouls_in_one_request():
    config = make_settings().providers["openrouter"]
    [payload] = NoulDecompositionAdapter().build_payloads(_canonical("p1", P1_INPUT), config, "respan/span-01-lite:free")
    questions = payload.body["questions"]
    assert list(questions) == ["relation__0", "relation__1", "relation__2"]
    assert all(q["type"] == "noul" and set(q["criteria"]) == {"true", "false"} for q in questions.values())
    assert payload.plan == {"relation": {"relation__0": "and", "relation__1": "or", "relation__2": "insufficient_evidence"}}
    assert isinstance(payload.body["state"], str)


def test_decomposition_keeps_native_noul_and_expands_p2_choices():
    config = make_settings().providers["openrouter"]
    [payload] = NoulDecompositionAdapter().build_payloads(_canonical("p2", P2_INPUT), config, "m")
    questions = payload.body["questions"]
    assert "mixed_lanes" in questions  # noul gốc giữ nguyên
    assert len([q for q in questions if q.startswith("performer__")]) == 3
    assert len([q for q in questions if q.startswith("evidence__")]) == 3
    assert "mixed_lanes" not in payload.plan


def test_decomposition_of_score_question():
    canonical = _canonical("p1", P1_INPUT)
    canonical.questions = {"level": score_question("Mức độ?", ["thấp", "vừa", "cao"])}
    canonical.answer_space = {"level": [0, 1, 2]}
    [payload] = NoulDecompositionAdapter().build_payloads(canonical, make_settings().providers["openrouter"], "m")
    assert payload.plan == {"level": {"level__0": 0, "level__1": 1, "level__2": 2}}


def test_chunking_splits_questions_and_plan():
    config = replace(make_settings().providers["openrouter"], max_questions=2)
    payloads = NoulDecompositionAdapter().build_payloads(_canonical("p1", P1_INPUT), config, "m")
    assert [len(p.body["questions"]) for p in payloads] == [2, 1]
    merged = {}
    for p in payloads:
        for orig, mapping in p.plan.items():
            merged.setdefault(orig, {}).update(mapping)
    assert len(merged["relation"]) == 3


def test_guard_blocks_forbidden_keys():
    with pytest.raises(PipelineError) as exc:
        assert_no_label_leak({"state": {"expected_relation": "and"}}, FORBIDDEN_PAYLOAD_KEYS)
    assert exc.value.code == ErrorCode.LABEL_LEAK_BLOCKED
    assert_no_label_leak({"state": "sạch", "questions": {}}, FORBIDDEN_PAYLOAD_KEYS)
