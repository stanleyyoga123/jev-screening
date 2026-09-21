from pydantic import BaseModel, ConfigDict, Field

from core.response import StandardResponse
from domains.screening.model import ScreeningQuestions
from integrations.jev import JevResponse


class ScreeningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    resume: str = Field(min_length=1, max_length=60000, pattern=r"\S")
    questions: ScreeningQuestions = Field(
        description="Map of question IDs to Jev question objects",
    )


ScreeningResponse = StandardResponse[JevResponse]
