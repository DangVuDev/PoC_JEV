"""Benchmark P2 Performer Lane qua API Decision Pipeline (PoC).

from_raw/to_raw la vi tri dong trong file CSV goc (khong loc theo split).

Vi du:
    python benchmark_p2.py --service_platform laya --from_raw 1 --to_raw 5 --output_folder out
    python benchmark_p2.py --service_platform openrouter --from_raw 6 --to_raw 10 --output_folder out --delay_s 1.5

File ket qua: <output_folder>/result_<from_raw>_<to_raw_thuc_te>.json
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_common import build_arg_parser, parse_bool_label, read_choice_answer, run_benchmark_segment

DEFAULT_CSV = str(Path(__file__).resolve().parent.parent / "p2_performer_lane_poc_200_1.csv")
ENDPOINT = "/api/v1/performer-lane/decide"


def build_row_fields(csv_row: dict[str, Any], response_body: dict[str, Any] | None) -> dict[str, Any]:
    answers = (response_body or {}).get("answers", {})
    fields: dict[str, Any] = {}

    for field_name, expected_raw in (
        ("performer", csv_row.get("expected_performer")),
        ("evidence", csv_row.get("expected_evidence")),
    ):
        predicted, confidence = read_choice_answer(answers.get(field_name))
        correct = (predicted == expected_raw) if (expected_raw and predicted is not None) else None
        fields[field_name] = {
            "predicted": predicted,
            "expected": expected_raw,
            "correct": correct,
            "confidence": confidence,
        }

    expected_mixed_raw = csv_row.get("expected_mixed_lanes")
    predicted_mixed, confidence_mixed = read_choice_answer(answers.get("mixed_lanes"))
    expected_mixed = parse_bool_label(expected_mixed_raw) if expected_mixed_raw not in (None, "") else None
    correct_mixed = (predicted_mixed == expected_mixed) if (expected_mixed is not None and predicted_mixed is not None) else None
    fields["mixed_lanes"] = {
        "predicted": predicted_mixed,
        "expected": expected_mixed,
        "correct": correct_mixed,
        "confidence": confidence_mixed,
    }

    return fields


def main() -> None:
    parser = build_arg_parser("P2 Performer Lane", DEFAULT_CSV)
    args = parser.parse_args()
    run_benchmark_segment(args, ENDPOINT, build_row_fields)


if __name__ == "__main__":
    main()
