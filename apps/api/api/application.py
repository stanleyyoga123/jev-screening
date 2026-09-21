from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.errors import FeatureNotImplementedError
from api.router import api_router


def create_app() -> FastAPI:
    application = FastAPI(title="Resume Screening API", version="0.1.0")
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

