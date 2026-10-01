"""Gop nhieu file result_<from>_<to>.json trong 1 thu muc thanh 1 bao cao tong hop.

Vi du:
    python summarize_results.py --folder p1_openrouter
    python summarize_results.py --folder p1_openrouter --output p1_openrouter/report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_segments(folder: Path) -> list[dict[str, Any]]:
    segments = []
    for path in sorted(folder.glob("result_*.json")):
        with path.open(encoding="utf-8") as handle:
            segments.append({"path": path.name, **json.load(handle)})
    return segments


def find_gaps(segments: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Trả về danh sách (from, to) các khoảng dòng KHÔNG có trong bất kỳ segment nào,
    tính trong phạm vi [min(from_raw), max(to_raw)] của toàn bộ segment đã có."""
    if not segments:
        return []
    covered: set[int] = set()
    for seg in segments:
        covered.update(range(seg["from_raw"], seg["to_raw"] + 1))
    full_min, full_max = min(s["from_raw"] for s in segments), max(s["to_raw"] for s in segments)
    missing = sorted(set(range(full_min, full_max + 1)) - covered)

    gaps: list[tuple[int, int]] = []
    for n in missing:
        if gaps and gaps[-1][1] == n - 1:
            gaps[-1] = (gaps[-1][0], n)
        else:
            gaps.append((n, n))
    return gaps


def merge_summary(segments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Gop summary tung field tu nhieu segment thanh 1 summary chung, cong don scored/correct."""
    merged: dict[str, dict[str, int]] = {}
    for seg in segments:
        for field_name, stat in seg.get("summary", {}).items():
            bucket = merged.setdefault(field_name, {"scored": 0, "correct": 0})
            bucket["scored"] += stat["scored"]
            bucket["correct"] += stat["correct"]
    result = {}
    for field_name, bucket in merged.items():
        accuracy = (bucket["correct"] / bucket["scored"]) if bucket["scored"] else None
        result[field_name] = {"scored": bucket["scored"], "correct": bucket["correct"], "accuracy": accuracy}
    return result


def collect_errors(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors = []
    for seg in segments:
        for sample in seg.get("samples", []):
            if sample.get("http_status") != 200:
                errors.append({"raw_number": sample["raw_number"], "sample_id": sample["sample_id"], "error": sample.get("error")})
    return errors


def total_samples(segments: list[dict[str, Any]]) -> int:
    return sum(seg["count"] for seg in segments)


def build_markdown(folder: Path, segments: list[dict[str, Any]]) -> str:
    gaps = find_gaps(segments)
    summary = merge_summary(segments)
    http_errors = collect_errors(segments)
    total = total_samples(segments)

    lines = [f"# Bao cao benchmark: {folder.name}", ""]
    lines.append(f"- So file ket qua: {len(segments)}")
    lines.append(f"- Tong so mau da chay: {total}")
    if segments:
        full_min, full_max = min(s["from_raw"] for s in segments), max(s["to_raw"] for s in segments)
        expected_total = full_max - full_min + 1
        lines.append(f"- Pham vi: dong {full_min} den {full_max} ({expected_total} dong)")
        if gaps:
            gap_text = ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in gaps)
            missing_count = sum(b - a + 1 for a, b in gaps)
            lines.append(f"- **THIEU {missing_count} dong, chua chay**: {gap_text}")
        else:
            lines.append("- Khong thieu dong nao trong pham vi tren.")
    lines.append(f"- Loi HTTP (khong tra duoc ket qua): {len(http_errors)}")
    lines.append("")

    lines.append("## Accuracy tong hop")
    lines.append("")
    lines.append("| Truong | Da cham diem | Dung | Accuracy |")
    lines.append("|---|---|---|---|")
    for field_name in sorted(summary):
        stat = summary[field_name]
        acc = f"{stat['accuracy']:.3f}" if stat["accuracy"] is not None else "null"
        lines.append(f"| {field_name} | {stat['scored']} | {stat['correct']} | {acc} |")
    lines.append("")

    lines.append("## Chi tiet tung file")
    lines.append("")
    lines.append("| File | Dong | So mau | Accuracy tung truong |")
    lines.append("|---|---|---|---|")
    for seg in segments:
        acc_parts = []
        for field_name, stat in seg.get("summary", {}).items():
            acc = f"{stat['accuracy']:.3f}" if stat["accuracy"] is not None else "null"
            acc_parts.append(f"{field_name}={acc}")
        lines.append(f"| {seg['path']} | {seg['from_raw']}-{seg['to_raw']} | {seg['count']} | {', '.join(acc_parts)} |")
    lines.append("")

    if http_errors:
        lines.append("## Mau loi HTTP")
        lines.append("")
        lines.append("| Dong | sample_id | Loi |")
        lines.append("|---|---|---|")
        for err in http_errors:
            lines.append(f"| {err['raw_number']} | {err['sample_id']} | `{json.dumps(err['error'], ensure_ascii=False)}` |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True, help="thu muc chua cac file result_<from>_<to>.json")
    parser.add_argument("--output", default=None, help="duong dan file bao cao .md (mac dinh: <folder>/report.md)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"Khong tim thay thu muc: {folder}", file=sys.stderr)
        sys.exit(1)

    segments = load_segments(folder)
    if not segments:
        print(f"Khong co file result_*.json nao trong {folder}", file=sys.stderr)
        sys.exit(1)

    report = build_markdown(folder, segments)
    output_path = Path(args.output) if args.output else folder / "report.md"
    output_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nDa ghi bao cao: {output_path}")


if __name__ == "__main__":
    main()
