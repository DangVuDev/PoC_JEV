"""Chốt chặn cuối cùng chống rò rỉ nhãn trước khi request rời hệ thống (BA mục 3.3)."""

from __future__ import annotations

from typing import Any, Iterable, Iterator

from ...errors import ErrorCode, PipelineError


def _iter_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _iter_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_keys(child)


def assert_no_label_leak(body: dict[str, Any], forbidden_keys: Iterable[str]) -> None:
    leaked = sorted(set(forbidden_keys).intersection(_iter_keys(body)))
    if leaked:
        raise PipelineError(ErrorCode.LABEL_LEAK_BLOCKED, f"payload chứa trường cấm: {', '.join(leaked)}")
