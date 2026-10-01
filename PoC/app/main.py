"""Điểm khởi tạo FastAPI.

Chạy: uvicorn app.main:create_app --factory --port 8010
Dùng factory để việc đọc .env chỉ xảy ra khi khởi động server, không xảy ra lúc import.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api import condition_relation, performer_lane, providers
from .config import Settings, load_settings
from .errors import ErrorCode, PipelineError
from .pipeline.executor.executor import RequestExecutor
from .pipeline.executor.registry import ProviderRegistry
from .pipeline.executor.transport import HttpTransport
from .pipeline.orchestrator import DecisionPipeline


def create_app(settings: Settings | None = None, transport: HttpTransport | None = None) -> FastAPI:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = settings or load_settings()
    transport = transport or HttpTransport()
    registry = ProviderRegistry(settings)
    pipeline = DecisionPipeline(registry, RequestExecutor(transport))

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            transport.close()

    app = FastAPI(title="Decision Pipeline PoC", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.registry = registry
    app.state.pipeline = pipeline

    app.include_router(condition_relation.router)
    app.include_router(performer_lane.router)
    app.include_router(providers.router)

    @app.get("/health", tags=["Health"])
    def health() -> dict:
        enabled = [p["name"] for p in registry.describe() if p["enabled"]]
        return {"status": "ok" if enabled else "degraded", "enabled_providers": enabled}

    @app.exception_handler(PipelineError)
    async def _pipeline_error(_request: Request, exc: PipelineError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.to_body())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "request không đúng định dạng",
                    "details": jsonable_encoder(exc.errors()),
                }
            },
        )

    return app
