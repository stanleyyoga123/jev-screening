from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from domains.screening.factory import get_screening_service
from domains.screening.model import ScreeningError, ScreeningTimeout
from domains.screening.schema import ScreeningRequest, ScreeningResponse
from domains.screening.service import ScreeningService


router = APIRouter(tags=["screening"])


@router.post("/screen", response_model=ScreeningResponse)
async def screen(
    request: ScreeningRequest,
    service: Annotated[ScreeningService, Depends(get_screening_service)],
) -> ScreeningResponse:
    try:
        result = await service.screen(request)
    except ScreeningTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except ScreeningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ScreeningResponse(success=True, data=result)
