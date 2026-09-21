from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from integrations.jev import Question

RequirementText = Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]
Outcome = Literal["meets", "partial", "does_not_meet", "insufficient_evidence"]


class CriteriaQuestion(Question):
    type: Literal["choice"] = "choice"
    instructions: RequirementText
    criteria: dict[Outcome, RequirementText] = Field(min_length=4, max_length=4)


CriteriaQuestions = Annotated[
    dict[
        Annotated[str, Field(pattern=r"^role_[a-z0-9_]{1,50}$")], CriteriaQuestion
    ],
    Field(min_length=1, max_length=20),
]


class GeneratedCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    questions: CriteriaQuestions


class CriteriaGenerationError(Exception):
    """The generation provider failed to return usable criteria."""


class CriteriaGenerationTimeout(CriteriaGenerationError):
    """The generation provider timed out."""
