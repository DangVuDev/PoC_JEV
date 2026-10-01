import pytest

from app.pipeline.normalizer import p1_condition_relation, p2_performer_lane
from app.pipeline.questions import answer_space_of, choice_question, noul_question, score_question
from app.schemas.internal import IntakeRecord
from tests.fixtures import P2_INPUT


def _record(task, data):
    return IntakeRecord(request_id="r", task=task, input=data)


P1_INPUT = {"clause_text": "A và B.", "left_condition": "A", "right_condition": "B"}


def test_p1_single_choice_with_fixed_options_in_order():
    req = p1_condition_relation.normalize(_record("p1", P1_INPUT))
    assert list(req.questions) == ["relation"]
    assert req.questions["relation"].type == "choice"
    assert req.answer_space["relation"] == ["and", "or", "insufficient_evidence"]
    assert "Vế 1: A" in req.state_text and "Vế 2: B" in req.state_text
    assert req.prompt_version == "p1.v1"


def test_p2_question_types_per_field():
    req = p2_performer_lane.normalize(_record("p2", P2_INPUT))
    assert {q: req.questions[q].type for q in req.questions} == {
        "performer": "choice", "evidence": "choice", "mixed_lanes": "noul",
    }


def test_p2_performer_options_are_member_ids_plus_insufficient():
    req = p2_performer_lane.normalize(_record("p2", P2_INPUT))
    assert req.answer_space["performer"] == ["pmkt_frontend", "pmkt_core", "insufficient_evidence"]
    assert "PMKT (Front-end)" in req.questions["performer"].criteria["pmkt_frontend"]
    assert req.answer_space["mixed_lanes"] == [True, False]


def test_p2_state_contains_row_subject_and_substeps_but_not_members():
    req = p2_performer_lane.normalize(_record("p2", P2_INPUT))
    assert "Mở webview ID Safe" in req.state_text
    assert "Chủ thể: Hệ thống" in req.state_text
    assert "pmkt_core" not in req.state_text


def test_normalize_is_deterministic():
    a = p2_performer_lane.normalize(_record("p2", P2_INPUT))
    b = p2_performer_lane.normalize(_record("p2", P2_INPUT))
    assert a == b


def test_builders_and_answer_space():
    assert answer_space_of(choice_question("q?", {"x": "", "y": "d"})) == ["x", "y"]
    assert answer_space_of(score_question("q?", ["thấp", "vừa", "cao"])) == [0, 1, 2]
    noul = noul_question("q?", "có", "không")
    assert noul.to_wire()["criteria"] == {"true": "có", "false": "không"}
    assert answer_space_of(noul) == [True, False]


@pytest.mark.parametrize("builder", [
    lambda: choice_question("q?", {"only": "one"}),
    lambda: choice_question("", {"a": "", "b": ""}),
    lambda: score_question("q?", ["one"]),
    lambda: noul_question("q?", "", "no"),
])
def test_builders_reject_invalid_questions(builder):
    with pytest.raises(ValueError):
        builder()
