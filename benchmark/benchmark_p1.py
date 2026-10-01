"""Benchmark P1 Condition Relation qua API Decision Pipeline (PoC).

Vi du:
    python benchmark_p1.py --service_platform laya --from_raw 1 --to_raw 5 --output_folder out
    python benchmark_p1.py --service_platform openrouter --from_raw 6 --to_raw 10 --output_folder out --delay_s 1.5

File ket qua: <output_folder>/result_<from_raw>_<to_raw_thuc_te>.json
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_common import build_arg_parser, read_choice_answer, run_benchmark_segment

DEFAULT_CSV = str(Path(__file__).resolve().parent.parent / "p1_condition_relation_poc_200_1.csv")
ENDPOINT = "/api/v1/condition-relation/decide"


def build_row_fields(csv_row: dict[str, Any], response_body: dict[str, Any] | None) -> dict[str, Any]:
    expected = csv_row.get("expected_relation")
    answer = (response_body or {}).get("answers", {}).get("relation")
    predicted, confidence = read_choice_answer(answer)

    correct = (predicted == expected) if (expected and predicted is not None) else None
    return {
        "relation": {
            "predicted": predicted,
            "expected": expected,
            "correct": correct,
            "confidence": confidence,
        }
    }


def main() -> None:
    parser = build_arg_parser("P1 Condition Relation", DEFAULT_CSV)
    args = parser.parse_args()
    run_benchmark_segment(args, ENDPOINT, build_row_fields)


if __name__ == "__main__":
    main()
