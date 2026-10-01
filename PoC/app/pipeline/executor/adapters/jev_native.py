"""Chiến lược A — native: provider hỗ trợ đủ choice/score/noul (Laya, Jev)."""

from __future__ import annotations

from typing import Any

from ....schemas.internal import CanonicalDecisionRequest, DecompositionPlan
from .base import ProviderAdapter


class JevNativeAdapter(ProviderAdapter):
    strategy = "jev_native"

    def translate_questions(
        self, request: CanonicalDecisionRequest
    ) -> tuple[dict[str, dict[str, Any]], DecompositionPlan]:
        return {qid: q.to_wire() for qid, q in request.questions.items()}, {}
