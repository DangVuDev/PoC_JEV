"""Log có cấu trúc theo từng chặng. Không bao giờ ghi API key hay body đầy đủ."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("decision_pipeline")


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))
