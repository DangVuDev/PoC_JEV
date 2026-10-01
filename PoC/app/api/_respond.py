from fastapi import Request
from fastapi.responses import JSONResponse

from ..schemas.request import DecideRequest


def decide(task: str, body: DecideRequest, request: Request) -> JSONResponse:
    output = request.app.state.pipeline.run(task, body)
    # Thông tin vận hành đi qua header để body giữ nguyên như provider trả về.
    headers = {
        "X-Request-ID": output.request_id,
        "X-Service-Platform": output.provider,
        "X-Strategy": output.strategy,
        "X-Provider-Latency-Ms": f"{output.latency_ms:.1f}",
    }
    return JSONResponse(content=output.body, headers=headers)
