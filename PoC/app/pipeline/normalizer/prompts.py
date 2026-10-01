"""Template prompt có phiên bản (BA mục 4.4).

Sửa nội dung prompt thì tạo phiên bản mới thay vì sửa phiên bản cũ, để kết quả đã
chạy vẫn tái lập được theo `prompt_version` trả trong response.
"""

from __future__ import annotations

P1_VERSION = "p1.v1"
P2_VERSION = "p2.v1"

PROMPTS: dict[str, dict] = {
    "p1.v1": {
        "state_template": "Câu điều khoản: {clause_text}\nVế 1: {left_condition}\nVế 2: {right_condition}",
        "relation": {
            "instructions": "Trong câu điều khoản, vế 1 và vế 2 có quan hệ logic gì với nhau?",
            "options": {
                "and": "cả hai vế phải được thỏa đồng thời (và, đồng thời, liệt kê cùng cấp bằng dấu phẩy)",
                "or": "chỉ cần thỏa một trong hai vế (hoặc)",
                "insufficient_evidence": "câu không nêu rõ cách kết hợp hai vế, không đủ căn cứ để kết luận",
            },
        },
    },
    "p2.v1": {
        "state_row": "Dòng mô tả bước: {row_text}",
        "state_subject": "Chủ thể: {subject}",
        "state_substeps": "Bước con cần xác định: {quotes}",
        "performer": {
            "instructions": "Cấu phần nào trực tiếp thực hiện bước được mô tả?",
            "insufficient_evidence": "không đủ căn cứ trong câu để xác định cấu phần thực hiện",
        },
        "evidence": {
            "instructions": "Căn cứ chính để xác định cấu phần thực hiện nằm ở đâu trong câu?",
            "options": {
                "object": "tên đối tượng, màn hình hoặc dữ liệu được nhắc tới (danh từ) cho biết cấu phần",
                "verb": "động từ hành động (hiển thị, lưu, kiểm tra, gửi, ...) cho biết cấu phần",
                "context": "không có từ khóa trực tiếp, phải suy ra từ ngữ cảnh xung quanh",
            },
        },
        "mixed_lanes": {
            "instructions": "Bước này có đồng thời chứa việc của phía client (giao diện) và phía server (xử lý nghiệp vụ) không?",
            "true": "bước trộn lẫn việc của nhiều tier (client và server)",
            "false": "bước chỉ thuộc một tier duy nhất",
        },
    },
}


def get_prompt(version: str) -> dict:
    if version not in PROMPTS:
        raise KeyError(f"không có prompt phiên bản '{version}'")
    return PROMPTS[version]
