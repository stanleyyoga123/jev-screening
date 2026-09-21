from pydantic import BaseModel, ConfigDict, Field, Json

from core.response import StandardResponse
from domains.screening.model import ScreeningQuestions
from integrations.jev import JevResponse


class ScreeningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    resume: str = Field(min_length=1, max_length=60000, pattern=r"\S")
    questions: Json[ScreeningQuestions] = Field(
        description="JSON string containing the Jev questions map, without a questions wrapper",
    )


ScreeningResponse = StandardResponse[JevResponse]
