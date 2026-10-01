"""Hàm dùng chung cho benchmark P1/P2: đọc CSV, gọi API, chấm điểm, ghi file kết quả.

Không phụ thuộc PoC/ hay laya-server/ về code — chỉ gọi HTTP tới API PoC đang chạy.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


def build_arg_parser(task_name: str, default_csv: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Benchmark {task_name} qua API Decision Pipeline (PoC)."
    )
    parser.add_argument("--service_platform", required=True, help="laya, openrouter, ...")
    parser.add_argument("--from_raw", type=int, default=1, help="dòng bắt đầu trong CSV (1-based, bao gồm)")
    parser.add_argument("--to_raw", type=int, default=None, help="dòng kết thúc trong CSV (1-based, bao gồm). Mặc định: hết file")
    parser.add_argument("--output_folder", required=True, help="thư mục ghi result_<from>_<to>.json")
    parser.add_argument("--csv", default=default_csv, help=f"đường dẫn file CSV nguồn (mặc định: {default_csv})")
    parser.add_argument("--base_url", default="http://127.0.0.1:8010", help="địa chỉ gốc API PoC")
    parser.add_argument("--delay_s", type=float, default=0.0, help="số giây nghỉ giữa 2 request liên tiếp")
    parser.add_argument("--timeout_s", type=float, default=120.0, help="timeout mỗi request (giây)")
    return parser


def read_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def select_range(rows: list[dict[str, Any]], from_raw: int, to_raw: int | None) -> list[dict[str, Any]]:
    """from_raw/to_raw là số dòng 1-based trong CSV (dòng 1 = bản ghi đầu tiên sau header)."""
    total = len(rows)
    if from_raw < 1:
        raise ValueError(f"--from_raw phải >= 1, nhận {from_raw}")
    end = total if to_raw is None else to_raw
    if end < from_raw:
        raise ValueError(f"--to_raw ({end}) phải >= --from_raw ({from_raw})")
    if from_raw > total:
        raise ValueError(f"--from_raw ({from_raw}) vượt quá tổng số dòng ({total})")
    end = min(end, total)
    return rows[from_raw - 1 : end]


def call_decide_api(base_url: str, endpoint_path: str, service_platform: str, input_json: Any, timeout_s: float) -> dict[str, Any]:
    """Gọi 1 request tới API, trả {'http_status', 'body'} (body là dict dù thành công hay lỗi)."""
    url = base_url.rstrip("/") + endpoint_path
    payload = json.dumps({"service_platform": service_platform, "input_json": input_json}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, method="POST", headers={"Content-Type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body_bytes = response.read()
            return {"http_status": response.status, "body": json.loads(body_bytes.decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except ValueError:
            body = {"raw_text": body_bytes.decode("utf-8", errors="replace")}
        return {"http_status": exc.code, "body": body}
    except urllib.error.URLError as exc:
        return {"http_status": None, "body": {"error": {"code": "CONNECTION_ERROR", "message": str(exc.reason)}}}


def read_choice_answer(answer: dict[str, Any] | None) -> tuple[Any, float | None]:
    """(giá trị, confidence) từ 1 answer chuẩn Jev (choice hoặc noul)."""
    if not isinstance(answer, dict):
        return None, None
    if "choice" in answer:
        probs = answer.get("probabilities") or {}
        choice = answer["choice"]
        confidence = probs.get(str(choice))
        if confidence is None:
            confidence = answer.get("answer_confidence")
        return choice, confidence
    if "noul" in answer:
        p = float(answer["noul"])
        return (p >= 0.5), max(p, 1.0 - p)
    return None, None


def parse_bool_label(raw: str) -> bool:
    return str(raw).strip().lower() == "true"


def run_benchmark_segment(
    args: argparse.Namespace,
    endpoint_path: str,
    build_row_fields: Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]],
) -> None:
    """Vòng lặp chung: đọc CSV -> chọn đoạn -> gọi API từng dòng -> chấm điểm -> ghi file.

    build_row_fields(csv_row, response_body_or_None) -> dict các trường nghiệp vụ đã chấm điểm
    cho MỘT dòng, dạng {field_name: {"predicted":..., "expected":..., "correct":..., "confidence":...}}.
    Trả {} nếu http lỗi (không có response hợp lệ để chấm).
    """
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Không tìm thấy file CSV: {csv_path}", file=sys.stderr)
        sys.exit(1)

    rows = read_csv_rows(csv_path)
    try:
        segment = select_range(rows, args.from_raw, args.to_raw)
    except ValueError as exc:
        print(f"Lỗi tham số: {exc}", file=sys.stderr)
        sys.exit(1)

    to_raw_actual = args.from_raw + len(segment) - 1
    output_dir = Path(args.output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"result_{args.from_raw}_{to_raw_actual}.json"

    samples: list[dict[str, Any]] = []
    for i, row in enumerate(segment):
        if i > 0 and args.delay_s > 0:
            time.sleep(args.delay_s)

        raw_number = args.from_raw + i
        sample_id = row.get("sample_id", f"row_{raw_number}")
        result = call_decide_api(args.base_url, endpoint_path, args.service_platform, row["input_json"], args.timeout_s)

        entry: dict[str, Any] = {
            "raw_number": raw_number,
            "sample_id": sample_id,
            "http_status": result["http_status"],
        }
        if result["http_status"] == 200:
            entry["fields"] = build_row_fields(row, result["body"])
            entry["response"] = result["body"]
        else:
            entry["fields"] = {}
            entry["error"] = result["body"]

        samples.append(entry)
        status_text = "OK" if result["http_status"] == 200 else f"LOI(HTTP {result['http_status']})"
        print(f"[{raw_number}/{to_raw_actual}] {sample_id}: {status_text}")

    summary = summarize(samples)
    output_doc = {
        "service_platform": args.service_platform,
        "csv": str(csv_path),
        "from_raw": args.from_raw,
        "to_raw": to_raw_actual,
        "count": len(samples),
        "summary": summary,
        "samples": samples,
    }
    output_path.write_text(json.dumps(output_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print(f"Tong {len(samples)} mau | loi HTTP {sum(1 for s in samples if s['http_status'] != 200)}")
    for field_name, stat in summary.items():
        acc = f"{stat['accuracy']:.3f}" if stat["accuracy"] is not None else "null"
        print(f"- {field_name}: accuracy {acc} ({stat['correct']}/{stat['scored']})")
    print(f"\nKet qua: {output_path}")


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    field_names: set[str] = set()
    for sample in samples:
        field_names.update(sample.get("fields", {}).keys())

    summary: dict[str, Any] = {}
    for field_name in sorted(field_names):
        scored = [
            s["fields"][field_name]
            for s in samples
            if field_name in s.get("fields", {}) and s["fields"][field_name].get("correct") is not None
        ]
        correct = sum(1 for f in scored if f["correct"])
        summary[field_name] = {
            "scored": len(scored),
            "correct": correct,
            "accuracy": (correct / len(scored)) if scored else None,
        }
    return summary
