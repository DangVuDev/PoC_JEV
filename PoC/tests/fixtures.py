"""Mẫu dữ liệu thật lấy từ 2 file CSV nguồn."""

import json

P1_INPUT = {
    "clause_text": "Là tài khoản có trạng thái hoạt động, không bị khóa ghi nợ, không đồng sở hữu và không có người giám hộ.",
    "left_condition": "có trạng thái hoạt động",
    "right_condition": "không bị khóa ghi nợ",
}

P2_INPUT = {
    "row_text": "Mở webview ID Safe",
    "subject": {"text": "Hệ thống", "resolution": "generic"},
    "substeps": [{"step_key": "4c491ddfa373:6", "quote": "Mở webview ID Safe", "operation": None, "object_labels": []}],
    "members": [
        {"id": "pmkt_frontend", "name": "PMKT (Front-end)", "tier": "client", "description": "Giao diện website và các màn hình nghiệp vụ cho người dùng"},
        {"id": "pmkt_core", "name": "PMKT (Core)", "tier": "server", "description": "Xử lý logic nghiệp vụ, lưu dữ liệu, hạch toán và tích hợp"},
    ],
    "hints": {},
}

# Nguyên một dòng CSV P1 (input_json dạng chuỗi, kèm nhãn): API phải bỏ qua các trường thừa.
P1_CSV_ROW = {
    "sample_id": "CR-001",
    "input_json": json.dumps(P1_INPUT, ensure_ascii=False),
    "pair_scope": "flat",
    "expected_relation": "and",
    "label_status": "curated",
}


def p1_request(provider: str, input_json=None) -> dict:
    return {"service_platform": provider, "input_json": input_json if input_json is not None else P1_INPUT}


def p2_request(provider: str, input_json=None) -> dict:
    return {"service_platform": provider, "input_json": input_json if input_json is not None else P2_INPUT}
