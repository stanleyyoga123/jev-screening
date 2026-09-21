from typing import Annotated

from fastapi import APIRouter, Depends

from domains.health.schema import HealthStatus
from domains.health.factory import get_health_service
from domains.health.service import HealthService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def health(service: Annotated[HealthService, Depends(get_health_service)]) -> HealthStatus:
    return service.check()
