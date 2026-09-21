import logging

import httpx
from pydantic import ValidationError

from domains.screening.model import ScreeningError, ScreeningTimeout
from domains.screening.schema import ScreeningRequest
from integrations.jev import JevProvider, JevResponse, JevResponseError


logger = logging.getLogger("ScreeningService")


class ScreeningService:
    def __init__(self, jev: JevProvider) -> None:
        self._jev = jev

    async def screen(self, request: ScreeningRequest) -> JevResponse:
        try:
            result = await self._jev.hit(state=request.resume, questions=request.questions)
        except httpx.TimeoutException as exc:
            raise ScreeningTimeout("Screening timed out") from exc
        except httpx.HTTPError as exc:
            raise ScreeningError("Screening provider failed") from exc
        except (ValidationError, JevResponseError) as exc:
            raise ScreeningError("Screening provider returned invalid answers") from exc
        logger.info("screening_completed question_count=%s", len(request.questions))
        return result
