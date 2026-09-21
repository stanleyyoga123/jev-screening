import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from core.response import StandardResponse
from domains.criteria.factory import get_criteria_service
from domains.criteria.model import CriteriaGenerationError, CriteriaGenerationTimeout
from domains.criteria.prompt import SYSTEM_PROMPT
from domains.criteria.schema import CriteriaResponse, GenerateCriteriaRequest, ValidateCriteriaRequest
from domains.criteria.service import CriteriaService


router = APIRouter(prefix="/criteria", tags=["criteria"])
logger = logging.getLogger("CriteriaRouter")


@router.post("/generate", response_model=CriteriaResponse)
async def generate(
    request: GenerateCriteriaRequest,
    service: Annotated[CriteriaService, Depends(get_criteria_service)],
) -> CriteriaResponse:
    try:
        criteria = await service.generate(request)
    except CriteriaGenerationTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except CriteriaGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CriteriaResponse(success=True, data=criteria)


@router.post("/validate", response_model=CriteriaResponse)
def validate(request: ValidateCriteriaRequest) -> CriteriaResponse:
    logger.info("criteria_validated question_count=%s", len(request.questions))
    return CriteriaResponse(success=True, data=request)


@router.get("/prompt", response_model=StandardResponse[str])
def prompt() -> StandardResponse[str]:
    return StandardResponse(success=True, data=SYSTEM_PROMPT)
