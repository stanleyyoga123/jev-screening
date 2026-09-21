import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.errors import FeatureNotImplementedError
from api.router import api_router
from api.middleware import RequestLoggingMiddleware
from config.logging import LoggingSettings
from config.application import ApplicationSettings
from core.logging import configure_logging


logger = logging.getLogger("Application")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    logger.info("application_started name=%s", application.title)
    try:
        yield
    finally:
        logger.info("application_stopped name=%s", application.title)


def create_app() -> FastAPI:
    settings = ApplicationSettings()
    configure_logging(LoggingSettings().log_level)
    application = FastAPI(
        title="Resume Screening API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.dev else None,
        redoc_url="/redoc" if settings.dev else None,
        openapi_url="/openapi.json" if settings.dev else None,
    )
    application.add_middleware(RequestLoggingMiddleware)
    application.include_router(api_router)

    @application.exception_handler(FeatureNotImplementedError)
    async def feature_not_implemented(
        request: Request, exc: FeatureNotImplementedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=501,
            content={"detail": str(exc)},
        )

    return application
