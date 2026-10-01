"""Provider giả lập, bám theo hành vi đã kiểm chứng bằng request thật (BA mục 0.4)."""

from __future__ import annotations

import json
from typing import Callable

import httpx

LAYA_HOST = "laya.test"
OPENROUTER_HOST = "openrouter.test"
OPENROUTER_KEY = "sk-or-v1-TESTKEY-1234567890abcdef"


class FakeLaya:
    """Laya /v1/systemone: nhận choice/score/noul, trả probabilities + answer_confidence."""

    def __init__(self, choice_probs: dict[str, dict[str, float]] | None = None, noul_prob: float = 0.2):
        self.choice_probs = choice_probs or {}
        self.noul_prob = noul_prob
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        answers = {}
        for qid, q in body["questions"].items():
            if q["type"] == "choice":
                options = list(q["criteria"])
                probs = self.choice_probs.get(qid) or {
                    o: (0.7 if i == 0 else 0.3 / (len(options) - 1)) for i, o in enumerate(options)
                }
                choice = max(probs, key=probs.get)
                answers[qid] = {"type": "choice", "choice": choice, "probabilities": probs,
                                "confidence": 0.41, "answer_confidence": max(probs.values())}
            elif q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": self.noul_prob, "confidence": 0.5}
            else:
                n = len(q["criteria"])
                probs = {str(i): (0.6 if i == n - 1 else 0.4 / (n - 1)) for i in range(n)}
                answers[qid] = {"type": "score", "score": n - 1, "probabilities": probs}
        return httpx.Response(200, json={
            "model": "laya-rl-agent", "answers": answers,
            "usage": {"input_tokens": 120, "output_tokens": 0},
            "routing": {"model": "multilingual"},
        })


class FakeRespan:
    """OpenRouter /api/alpha/decisions với model Respan: chỉ nhận noul, criteria {true,false}, state là chuỗi."""

    def __init__(self, noul_fn: Callable[[str, dict], float] | None = None, api_key: str = OPENROUTER_KEY,
                 status_sequence: list[int] | None = None):
        self.noul_fn = noul_fn or (lambda qid, q: 0.6 if qid.endswith("__0") else 0.1)
        self.api_key = api_key
        self.status_sequence = list(status_sequence or [])
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization") != f"Bearer {self.api_key}":
            return httpx.Response(401, json={"error": {"message": "Missing Authentication header", "code": 401}})
        if self.status_sequence:
            status = self.status_sequence.pop(0)
            if status != 200:
                return httpx.Response(status, json={"error": {"message": f"simulated {status}", "code": status}})
        body = json.loads(request.content)
        self.requests.append(body)
        if not isinstance(body.get("state"), str):
            return _error(400, "Respan state must be a string or an object with only input (a message array) and output (a message)")
        for qid, q in body["questions"].items():
            if q.get("type") != "noul":
                return _error(400, f'Respan only accepts noul questions whose instructions and criteria are plain strings (question "{qid}")')
            if not isinstance(q.get("criteria"), dict) or set(q["criteria"]) != {"true", "false"}:
                return _error(400, f"invalid criteria for {qid}")
        answers = {qid: {"type": "noul", "noul": self.noul_fn(qid, q)} for qid, q in body["questions"].items()}
        return httpx.Response(200, json={
            "model": "respan/span-01-lite-20260925", "answers": answers,
            "usage": {"input_tokens": 60 * len(answers), "output_tokens": 0, "cost": 0},
            "provider": "Respan",
        })


def _error(status: int, message: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"message": message, "code": status}})


def router(laya: FakeLaya, respan: FakeRespan) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == LAYA_HOST:
            return laya(request)
        if request.url.host == OPENROUTER_HOST:
            return respan(request)
        return httpx.Response(404)

    return httpx.MockTransport(handle)
