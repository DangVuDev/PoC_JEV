"""Hợp đồng request (BA mục 2.2): mỗi request là một mẫu, chỉ gồm service_platform và input_json.

Trường thừa (sample_id, expected_*, options, ...) bị bỏ qua, nên client có thể gửi
nguyên một dòng CSV mà không cần lọc trước.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DecideRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    service_platform: str = Field(min_length=1)
    input_json: dict[str, Any] | str
