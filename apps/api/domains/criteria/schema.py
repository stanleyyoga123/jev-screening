from pydantic import BaseModel, ConfigDict, Field, Json

from core.response import StandardResponse
from domains.criteria.model import CriteriaQuestions, GeneratedCriteria


class GenerateCriteriaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    job_description: str = Field(min_length=1, max_length=30000, pattern=r"\S")


class ValidateCriteriaRequest(GeneratedCriteria):
    questions: CriteriaQuestions | Json[CriteriaQuestions]


CriteriaResponse = StandardResponse[GeneratedCriteria]
