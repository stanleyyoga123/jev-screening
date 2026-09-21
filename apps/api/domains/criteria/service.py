import logging

import httpx
from pydantic import ValidationError

from domains.criteria.model import (
    CriteriaGenerationError,
    CriteriaGenerationTimeout,
    GeneratedCriteria,
)
from domains.criteria.prompt import SYSTEM_PROMPT
from domains.criteria.schema import GenerateCriteriaRequest
from integrations.generator import GeneratorMessage, GeneratorProvider


logger = logging.getLogger("CriteriaService")


class CriteriaService:
    def __init__(self, generator: GeneratorProvider) -> None:
        self._generator = generator

    async def generate(self, request: GenerateCriteriaRequest) -> GeneratedCriteria:
        try:
            result = await self._generator.hit([
                GeneratorMessage(role="system", content=SYSTEM_PROMPT),
                GeneratorMessage(role="user", content=request.job_description),
            ])
            criteria = GeneratedCriteria.model_validate_json(result.content)
            logger.info("criteria_generated question_count=%s", len(criteria.questions))
            return criteria
        except httpx.TimeoutException as exc:
            raise CriteriaGenerationTimeout("Criteria generation timed out") from exc
        except httpx.HTTPError as exc:
            raise CriteriaGenerationError("Criteria generation provider failed") from exc
        except ValidationError as exc:
            logger.warning("criteria_generation_invalid_output")
            raise CriteriaGenerationError(
                "The model did not return valid questions for the job description"
            ) from exc
