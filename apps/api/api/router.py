from fastapi import APIRouter

from domains.criteria.router import router as criteria_router
from domains.documents.router import router as documents_router
from domains.health.router import router as health_router
from domains.screening.router import router as screening_router


api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(criteria_router)
api_router.include_router(screening_router)
