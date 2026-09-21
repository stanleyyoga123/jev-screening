from typing import Annotated

from fastapi import APIRouter, Depends

from domains.screening.factory import get_screening_service
from domains.screening.service import ScreeningService


router = APIRouter(prefix="", tags=["screening"])


@router.post("/screen", status_code=501, response_model=None)
async def screen(
    service: Annotated[ScreeningService, Depends(get_screening_service)],
) -> None:
    await service.screen()
