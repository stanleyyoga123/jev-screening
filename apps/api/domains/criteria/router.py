from typing import Annotated

from fastapi import APIRouter, Depends

from domains.criteria.factory import get_criteria_service
from domains.criteria.service import CriteriaService


router = APIRouter(prefix="/criteria", tags=["criteria"])


@router.post("/generate", status_code=501, response_model=None)
async def generate(
    service: Annotated[CriteriaService, Depends(get_criteria_service)],
) -> None:
    await service.generate()


@router.post("/validate", status_code=501, response_model=None)
async def validate(
    service: Annotated[CriteriaService, Depends(get_criteria_service)],
) -> None:
    await service.validate()


@router.get("/prompt", status_code=501, response_model=None)
async def prompt(
    service: Annotated[CriteriaService, Depends(get_criteria_service)],
) -> None:
    await service.prompt()
