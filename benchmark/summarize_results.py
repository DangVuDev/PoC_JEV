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


def dedupe_samples_by_raw_number(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nếu 2 file có đoạn chồng lấn (vd result_51_60 và result_51_70), giữ lại bản ghi
    của file xuất hiện SAU trong danh sách (sort theo tên file = sort theo thời gian tạo
    gần đúng do đặt tên result_<from>_<to>), để báo cáo không đếm trùng 1 dòng CSV 2 lần."""
    by_raw: dict[int, dict[str, Any]] = {}
    for seg in segments:
        for sample in seg.get("samples", []):
            by_raw[sample["raw_number"]] = sample
    return [by_raw[n] for n in sorted(by_raw)]


def find_overlaps(segments: list[dict[str, Any]]) -> list[tuple[str, str, int, int]]:
    """Danh sách (file_a, file_b, from, to) các khoảng dòng bị khai báo trong > 1 file."""
    counted: dict[int, list[str]] = {}
    for seg in segments:
        for n in range(seg["from_raw"], seg["to_raw"] + 1):
            counted.setdefault(n, []).append(seg["path"])
    overlapping_lines = sorted(n for n, files in counted.items() if len(files) > 1)

    overlaps: list[tuple[str, str, int, int]] = []
    i = 0
    while i < len(overlapping_lines):
        start = overlapping_lines[i]
        end = start
        while i + 1 < len(overlapping_lines) and overlapping_lines[i + 1] == end + 1:
            i += 1
            end = overlapping_lines[i]
        files = sorted(set(counted[start]))
        overlaps.append((", ".join(files), "", start, end))
        i += 1
    return overlaps


def merge_summary(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Tính summary tổng hợp trực tiếp từ danh sách mẫu ĐÃ khử trùng lặp theo raw_number."""
    merged: dict[str, dict[str, int]] = {}
    for sample in samples:
        for field_name, field in sample.get("fields", {}).items():
            if field.get("correct") is None:
                continue
            bucket = merged.setdefault(field_name, {"scored": 0, "correct": 0})
            bucket["scored"] += 1
            bucket["correct"] += 1 if field["correct"] else 0
    result = {}
    for field_name, bucket in merged.items():
        accuracy = (bucket["correct"] / bucket["scored"]) if bucket["scored"] else None
        result[field_name] = {"scored": bucket["scored"], "correct": bucket["correct"], "accuracy": accuracy}
    return result


def collect_errors(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"raw_number": s["raw_number"], "sample_id": s["sample_id"], "error": s.get("error")}
        for s in samples
        if s.get("http_status") != 200
    ]


def build_markdown(folder: Path, segments: list[dict[str, Any]]) -> str:
    gaps = find_gaps(segments)
    overlaps = find_overlaps(segments)
    deduped_samples = dedupe_samples_by_raw_number(segments)
    summary = merge_summary(deduped_samples)
    http_errors = collect_errors(deduped_samples)
    total = len(deduped_samples)

    lines = [f"# Bao cao benchmark: {folder.name}", ""]
    lines.append(f"- So file ket qua: {len(segments)}")
    lines.append(f"- Tong so mau da chay (da khu trung lap): {total}")
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
        if overlaps:
            lines.append(f"- **CHONG LAP** (da khu trung, giu ban ghi tu file xuat hien sau trong danh sach ten file):")
            for files, _, a, b in overlaps:
                rng = f"{a}-{b}" if a != b else str(a)
                lines.append(f"  - dong {rng}: xuat hien trong {files}")
        else:
            lines.append("- Khong co doan nao bi chay trung lap.")
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
