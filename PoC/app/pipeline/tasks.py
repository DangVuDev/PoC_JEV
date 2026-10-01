"""Registry bài toán: gom mọi thứ đặc thù của P1/P2 vào một chỗ.

Các chặng còn lại chỉ đọc TaskDefinition, nên thêm bài toán mới là thêm một
normalizer và một mục ở đây, không phải sửa intake/executor/response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..errors import PipelineError
from ..schemas.internal import CanonicalDecisionRequest, IntakeRecord, Task
from .normalizer import p1_condition_relation as p1
from .normalizer import p2_performer_lane as p2

# Trường nhãn/metadata của CSV nguồn: không bao giờ được xuất hiện trong payload gửi provider.
FORBIDDEN_PAYLOAD_KEYS = (
    "sample_id", "split", "label_status", "pair_scope",
    "expected_relation", "expected_performer", "expected_evidence", "expected_mixed_lanes",
)


@dataclass(frozen=True)
class TaskDefinition:
    name: Task
    input_fields: tuple[str, ...]
    validate_input: Callable[[dict[str, Any]], PipelineError | None]
    normalize: Callable[[IntakeRecord], CanonicalDecisionRequest]
    prompt_version: str


TASKS: dict[str, TaskDefinition] = {
    "p1": TaskDefinition("p1", p1.INPUT_FIELDS, p1.validate_input, p1.normalize, p1.P1_VERSION),
    "p2": TaskDefinition("p2", p2.INPUT_FIELDS, p2.validate_input, p2.normalize, p2.P2_VERSION),
}


def get_task(name: str) -> TaskDefinition:
    return TASKS[name]
