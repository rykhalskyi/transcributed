from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from transcributed.api.routes import nas, projects, runs, tasks, workers
from transcributed.config import get_settings
from transcributed.db import engine
from transcributed.errors import AppError
from transcributed.logging import configure_logging
from transcributed.messaging.publisher import TaskPublisher
from transcributed.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    publisher = TaskPublisher(
        url=settings.rabbitmq_url,
        exchange_name=settings.rabbitmq_exchange,
        jobs_queue=settings.rabbitmq_jobs_queue,
        enabled=settings.rabbitmq_enabled,
        connect_timeout_seconds=settings.rabbitmq_connect_timeout_seconds,
    )
    await publisher.connect()
    app.state.publisher = publisher
    try:
        yield
    finally:
        await publisher.close()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Transcributed API",
        version="0.2.1",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    app.include_router(projects.router, prefix=settings.api_prefix)
    app.include_router(runs.router, prefix=settings.api_prefix)
    app.include_router(tasks.router, prefix=settings.api_prefix)
    app.include_router(nas.router, prefix=settings.api_prefix)
    app.include_router(workers.router, prefix=settings.api_prefix)

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        content: dict[str, object] = {"detail": exc.message}
        if exc.details is not None:
            content["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/readyz", response_model=HealthResponse)
    async def readyz(request: Request) -> HealthResponse:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

        publisher = getattr(request.app.state, "publisher", None)
        if settings.rabbitmq_enabled and (
            publisher is None or not await publisher.ensure_connected()
        ):
            raise HTTPException(status_code=503, detail="task queue unavailable")
        return HealthResponse(status="ok")

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
