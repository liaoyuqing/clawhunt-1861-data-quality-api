"""FastAPI application factory."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import data_quality, health
from app.config import get_settings
from app.di import DbComposer
from app.errors import AppError
from app.schemas.envelope import ErrorBody

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def create_app(composer: object | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Member-space data quality dashboard API",
        version=__version__,
        description=(
            "Aggregate endpoint behind the management dashboard's profile-completeness panel. "
            "Reads the S2-CRM mirror read-only and takes its field list from the metric-caliber "
            "library, so a new caliber version changes the numbers without a redeploy."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.composer = composer or DbComposer(ttl_seconds=settings.cache_ttl_seconds)

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[object]]
    ) -> object:
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id  # type: ignore[attr-defined]
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        body = ErrorBody(
            code=exc.code,
            message=exc.message,
            request_id=getattr(request.state, "request_id", ""),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(data_quality.router, prefix=settings.api_prefix)
    return app


app = create_app()
